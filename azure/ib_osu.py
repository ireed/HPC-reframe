# Copyright 2016-2021 Swiss National Supercomputing Centre (CSCS/ETH Zurich)
# ReFrame Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import reframe as rfm
import reframe.utility.sanity as sn
import inspect
import reframe.core.config as cfg
import pprint
import reframe.utility.osext as osext
import sys
import reframe.utility as util
import os
import re
import subprocess
from reframe.core.backends import getlauncher


class fetch_osu_benchmarks(rfm.RunOnlyRegressionTest):
   descr = 'Fetch OSU benchmarks'
   version = variable(str, value='5.6.2')
   executable = 'wget'
   executable_opts = [
      f'http://mvapich.cse.ohio-state.edu/download/mvapich/osu-micro-benchmarks-{version}.tar.gz' 
   ]
   local = True

   @sanity_function
   def validate_download(self):
      return sn.assert_eq(self.job.exitcode, 0)


class build_osu_benchmarks(rfm.CompileOnlyRegressionTest):
   descr = 'Build OSU benchmarks'
   build_system = 'Autotools'
   build_prefix = variable(str)
   osu_benchmarks = fixture(fetch_osu_benchmarks, scope='session')

   @run_before('compile')
   def prepare_build(self):
      tarball = f'osu-micro-benchmarks-{self.osu_benchmarks.version}.tar.gz'
      self.build_prefix = tarball[:-7]  # remove .tar.gz extension

      fullpath = os.path.join(self.osu_benchmarks.stagedir, tarball)
      self.prebuild_cmds = [
         f'cp {fullpath} {self.stagedir}',
         f'tar xzf {tarball}',
         f'cd {self.build_prefix}'
      ]
      # Flags assume MPI is installed and loaded (ex: 'module load mpi/hpcx')
      self.build_system.cc = "mpicc"
      self.build_system.cxx = 'mpic++'
      self.build_system.ftn = 'mpifort'
      self.build_system.max_concurrency = 8

   @sanity_function
   def validate_build(self):
        # If compilation fails, the test would fail in any case, so nothing to
        # further validate here.
      return True

class IBstat_test(rfm.RunOnlyRegressionTest):
   # This test gets the expected interconnect speed by running IB stat on one
   #   node in the partition.
   descr = 'Get IB speed'
   IB_RATE = variable(str)
   IB_RATE = '0'
   NODELIST = variable(list)
   NODELIST = []
   nodelist_file ="reframe_nodelist.txt"

   @run_before('run')
   def prepare_run(self):
      #self.job.launcher = getlauncher('mpiexec')()
      #ireed: todo - change after job.node_numtasks issue is resolved
      self.executable = f"ibstat\nsrun hostname | sort > {self.nodelist_file}"

   #ireed: todo - remove this function after job.nodelist issue is resolved
   @run_after('run')
   def get_nodelist(self):
   # converts a file containing the jobs nodes into a list
      with osext.change_dir(self.stagedir):
         fp = open(self.nodelist_file,'r')
         nodes = fp.read()
         self.NODELIST = nodes.split('\n')
         del self.NODELIST[len(self.NODELIST)-1]
         print(self.NODELIST)
         fp.close()

   @sanity_function
   def validate_results(self):
       # Get node_data
      vm_info = self.current_system.node_data
      if 'runtime_data' not in self.current_system.node_data:
         self.current_system.node_data['runtime_data'] = {}
      self.current_system.node_data['runtime_data']['accelnet'] = True

      regex = r'CA\s+(?P<device_name>\S+)(.|\n)*?State:\s+(?P<device_state>\S+)(.|\n)*?Physical state:\s+(?P<device_pstate>\S+)(.|\n)*?Rate:\s+(?P<device_rate>\S+)(.|\n)*?Link layer:\s+(?P<device_type>\S+)'
      device_name = sn.extractall( regex, self.stdout, "device_name", str)
      device_state = sn.extractall( regex, self.stdout, "device_state", str)
      device_pstate = sn.extractall( regex, self.stdout, "device_pstate", str)
      device_rate = sn.extractall( regex, self.stdout, "device_rate", str)
      device_ll = sn.extractall( regex, self.stdout, "device_type", str)

      #ireed
      rate = device_rate[0]
      print("Device Names: {}".format(device_name))
      print("Device Link Layer: {}".format(device_ll))
      print("Device Rate: {}".format(device_rate))


      if sn.all(sn.map(lambda x: sn.assert_eq(x, 'Active'),device_state)) == False:
      #ireed: get info to give a more detailed error message
         mismatch = 0
         for val in device_state:
            if 'Active' != val:
               mismatch = mismatch + 1
         print("Error: {} nodes have a different state than node {}".format(mismatch,self.NODELIST[0]))
         return False

      if sn.all(sn.map(lambda x: sn.assert_eq(x, device_rate[0]),device_rate)) == False:
         mismatch = 0
         for val in device_rate:
            if device_rate[0] != val:
               mismatch = mismatch + 1
         print("Error: {} nodes have a different rate than node {}".format(mismatch,self.NODELIST[0]))
         return False


      self.IB_RATE = str(rate)

      # Loop through the devices found and verify that they properly report their values.
      ib_names = []
      ib_states = []
      ib_pstates = []
      ib_rates = []
      eth_names = []
      eth_states = []
      eth_pstates = []
      eth_rates = []

      for x,ll in enumerate(device_ll):
         print("Link Layer: {}, Device: {}, Rate: {}, State: {}, Physical State: {}".format(ll,device_name[x],device_rate[x],device_state[x],device_pstate[x]))
            # Separate devices based on link layer type
         if ll == "InfiniBand":
            ib_names.append(device_name[x])
            ib_rates.append(device_rate[x])
            ib_states.append(device_state[x])
            ib_pstates.append(device_pstate[x])
         elif ll == "Ethernet":
            eth_names.append(device_name[x])
            eth_rates.append(device_rate[x])
            eth_states.append(device_state[x])
            eth_pstates.append(device_pstate[x])
         else:
            print("Undefined Link Layer: {}".format(ll))
         return sn.all([
            #ireed: todo - adjust for multi-node jobs
            sn.assert_eq(sn.count(ib_names), vm_info['nhc_values']['ib_count'],msg='Found {} IB cards, but expected {}'.format(sn.count(ib_names), vm_info['nhc_values']['ib_count'])),
            sn.all(sn.map(lambda x: sn.assert_eq(x, vm_info['nhc_values']['ib_rate']),ib_rates)),
            sn.all(sn.map(lambda x: sn.assert_eq(x, vm_info['nhc_values']['ib_state']),ib_states)),
            sn.all(sn.map(lambda x: sn.assert_eq(x, vm_info['nhc_values']['ib_pstate']),ib_pstates))

         ])
      else:
         print("ib_count not found in vm_info['nhc_values']")
         return sn.assert_eq(sn.count(ib_names), 0)


class OSUBenchmarkTestBase(rfm.RunOnlyRegressionTest):
   '''Base class of OSU benchmarks runtime tests'''

   valid_systems = ['*']
   valid_prog_environs = ['*']
   num_tasks = 2
   num_tasks_per_node = 1
   exclusive_access = True
   #osu_dir = '$HPCX_OSU_DIR'
   osu_binaries = fixture(build_osu_benchmarks, scope='environment')
   # get interconnect speed from previous test
   ib_stat = fixture(IBstat_test, scope='environment')

   @sanity_function
   def validate_test(self):
      #return sn.assert_found(r'^8', self.stdout)
      return sn.assert_eq(self.job.exitcode, 0)





@rfm.simple_test
class osu_bandwidth_test(OSUBenchmarkTestBase):
   descr = 'OSU bandwidth test, symmetric node pairs'

   outfiles = []

   @run_after('compile')
   def set_test_flags(self):
      self.job.options = ['--time=02:00']
      #self.job.options.append('--array=1-2')
      self.job.options.append('--ntasks={}'.format(len(self.ib_stat.NODELIST)))
      #ireed: we want to use the same nodes that were used for the ibstat test
      #self.job.options.append('--nodelist={}'.format(','.join(self.ib_stat.NODELIST)))
      

   @run_before('run')
   def prepare_run(self):
      #ireed: srun may not work if MPI does not have PMIx
      self.job.launcher = getlauncher('mpiexec')()
      #ireed: use pre-installed OSU from module load mpi/hpcx
      #osu_dir = "$HPCX_OSU_DIR"  
      #ireed: or, use OSU that was downloaded in fetch_osu_benchmark test
      osu_dir = os.path.join(self.osu_binaries.stagedir,
            self.osu_binaries.build_prefix, 'mpi', 'pt2pt'  )

      self.executable = os.path.join(osu_dir, 'osu_bw')
      self.executable_opts = ['-x', '100', '-i', '1000', '-m', '1048576:']
      #util.osext.run_command('ls')
      #print(self.job.nodelist)

      if len(self.ib_stat.NODELIST) <= 2:
         return
      else:
         #ireed: we need to manually create the run script
         opts = ' '.join(self.executable_opts)
         self.executable_opts = []
         prog = self.executable
         self.executable = self.create_run_command(prog,opts)


   def create_run_command(self,prog,opts):
   #partition the num_nodes by 2, then pair nodes for bw test
      cmd = ''
      tmp = ''
      nodelist = self.ib_stat.NODELIST
      half = int(len(nodelist)/2)
      for i in range(0,half):
         outfile = str(nodelist[i])+"_to_"+str(nodelist[i+half])
         #mpiexec launcher includes 'mpiexec -n 2' by default, so append
         tmp = tmp + " -host " + nodelist[i] + ',' + nodelist[i+half]
         tmp = tmp + ' ' + prog + ' ' + opts + ' > ' + outfile + '\n'
         cmd = cmd + tmp
         self.outfiles.append(outfile)
         tmp = "mpiexec -n 2"
      cmd = cmd + "wait\n"
      if(len(nodelist)%2) == 1:
      # odd number of nodes; therefore, 1 job must be ran serially
         outfile = str(nodelist[len(nodelist)-1])+"_to_"+str(nodelist[half])
         tmp = "mpiexec -n 2 -host "
         tmp = tmp + nodelist[len(nodelist)-1] + "," + nodelist[0]
         tmp = tmp + ' ' + prog + ' ' + opts + ' > ' + outfile + '\n'
         cmd = cmd + tmp
         self.outfiles.append(outfile)
      return cmd

   #@performance_function('GB/s')
   def get_bandwidth(self,filename):
   #ireed: todo - find out how to fail after perf_function
      if os.path.getsize(filename) == 0:
         print("Error: Node pair {} failed".format(filename))
         return False
      with open(str(filename), mode='r') as fp:
         data = fp.read()
      #print(data)
      data_list = data.split('\n')
      bw = [s for s in data_list if '4194304' in s]
      bw = re.split(' +', bw[0])
      gbs = float(float(bw[1]) * 8 / 1000)
      gbs = float(f'{gbs:.2f}')
      return gbs

   @sanity_function
   def validate_test(self):
      sn.assert_ne(self.job.exitcode, 0, "Error OSU test failed")
      #fail if test is slower that 95% of interconect rate
      lower = float(float(self.ib_stat.IB_RATE) * .95)
      # 100% interconnect speed is not possible, so fail
      upper = float(float(self.ib_stat.IB_RATE) * .99)
      #print(self.ib_stat.IB_RATE)
      if len(self.ib_stat.NODELIST) <= 2:
         gbs = self.get_bandwidth(self.stdout)
         return sn.assert_bounded(gbs,lower,upper,
            'Bandwidth performance failed: {}Gb/s is outside of error margin' + 
            ' for {}Gb/s connection.'.format(gbs,self.ib_stat.IB_RATE))

      gbs_list = []
      fails = []
      avg_bw = float(0)
      for filename in self.outfiles:
         gbs = self.get_bandwidth(filename)
         if gbs == False:
            return False
         gbs_list.append(gbs)
         avg_bw = avg_bw + gbs
      avg_bw = avg_bw / float(len(gbs_list))

      succ = True
      for i in range(0,len(gbs_list)):
         if (gbs_list[i]>upper) or (gbs_list[i]<lower):
            succ = False
            # record all failing pairs
            fails.append(self.outfiles[i])  

      if succ == False:
         print("Bandwidth performance failed. Node pairs that are outside " +
            "of the error margin for the {}Gb/s connection:\n{}\n".format(self.ib_stat.IB_RATE,fails))
         return False
      else:
         print("Average bandwidth for all test pairs: {} Gb/s\n".format(float(f'{avg_bw:.2f}')))
         return True




@rfm.simple_test
class osu_bandwidth_test_round_2(OSUBenchmarkTestBase):
   descr = 'OSU bandwidth test, ring node pairs'
   # same as previous OSU b/w test, but with different node pairs
   outfiles = []

   @run_after('compile')
   def set_test_flags(self):
      self.job.options = ['--time=02:00']
      #self.job.options.append('--array=1-2')
      self.job.options.append('--ntasks={}'.format(len(self.ib_stat.NODELIST)))
      #ireed: we want to use the same nodes that were used for the ibstat test
      #self.job.options.append('--nodelist={}'.format(','.join(self.ib_stat.NODELIST)))
      

   @run_before('run')
   def prepare_run(self):
      # test is not needed if there are only 2 nodes
      if len(self.ib_stat.NODELIST) <= 2:
         return True
      self.job.launcher = getlauncher('mpiexec')()
      #ireed: use pre-installed OSU from module load mpi/hpcx
      #osu_dir = "$HPCX_OSU_DIR"  
      #ireed: or, use OSU that was downloaded in fetch_osu_benchmark test
      osu_dir = os.path.join(self.osu_binaries.stagedir,
            self.osu_binaries.build_prefix, 'mpi', 'pt2pt'  )

      self.executable = os.path.join(osu_dir, 'osu_bw')
      self.executable_opts = ['-x', '100', '-i', '1000', '-m', '1048576:']

      #ireed: manually create the run script
      opts = ' '.join(self.executable_opts)
      self.executable_opts = []
      prog = self.executable
      self.executable = self.create_run_command(prog,opts)


   def create_run_command(self,prog,opts):
   #partition the num_nodes by 2, then pair nodes for bw test
      cmd = ''
      tmp = ''
      nodelist = self.ib_stat.NODELIST
      half = int(len(nodelist)/2)
      for i in range(0,half):
         outfile = str(nodelist[i])+"_to_"+str(nodelist[i+half])
         #mpiexec launcher includes 'mpiexec -n 2' by default, so append
         tmp = tmp + " -host " + nodelist[2*i] + ',' + nodelist[(2*i)+1]
         tmp = tmp + ' ' + prog + ' ' + opts + ' > ' + outfile + '\n'
         cmd = cmd + tmp
         self.outfiles.append(outfile)
         tmp = "mpiexec -n 2"
      cmd = cmd + "wait\n"
      if(len(nodelist)%2) == 1:
      # odd number of nodes; therefore, 1 job must be ran serially
         outfile = str(nodelist[len(nodelist)-1])+"_to_"+str(nodelist[0])
         tmp = "mpiexec -n 2 -host "
         tmp = tmp + nodelist[len(nodelist)-1] + "," + nodelist[0]
         tmp = tmp + ' ' + prog + ' ' + opts + ' > ' + outfile + '\n'
         cmd = cmd + tmp
         self.outfiles.append(outfile)
      return cmd

   #@performance_function('GB/s')
   def get_bandwidth(self,filename):
   #ireed: todo - find out how to fail after perf_function
      with open(str(filename), mode='r') as fp:
         data = fp.read()
      #print(data)
      data_list = data.split('\n')
      bw = [s for s in data_list if '4194304' in s]
      bw = re.split(' +', bw[0])
      gbs = float(float(bw[1]) * 8 / 1000)
      gbs = float(f'{gbs:.2f}')
      return gbs

   @sanity_function
   def validate_test(self):
      if len(self.ib_stat.NODELIST) <= 2:
         return True
      sn.assert_ne(self.job.exitcode, 0, "Error OSU test failed")
      #fail if test is slower that 95% of interconect rate
      lower = float(float(self.ib_stat.IB_RATE) * .95)
      # 100% interconnect speed is not possible, so fail
      upper = float(float(self.ib_stat.IB_RATE) * .99)

      gbs_list = []
      fails = []
      avg_bw = float(0)
      for filename in self.outfiles:
         gbs = self.get_bandwidth(filename)
         gbs_list.append(gbs)
         avg_bw = avg_bw + gbs
      avg_bw = avg_bw / float(len(gbs_list))

      succ = True
      for i in range(0,len(gbs_list)):
         if (gbs_list[i]>upper) or (gbs_list[i]<lower):
            succ = False
            # record all failing node pairs
            fails.append(self.outfiles[i])  

      if succ == False:
         print("Bandwidth performance failed. Node pairs that are outside " +
            "of the error margin for the {}Gb/s connection:\n{}\n".format(self.ib_stat.IB_RATE,fails))
         return False
      else:
         print("Average bandwidth for all test pairs: {} Gb/s\n".format(float(f'{avg_bw:.2f}')))
         return True

