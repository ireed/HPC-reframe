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
   @run_before('run')
   def prepare_run(self):
      #self.job.launcher = getlauncher('mpiexec')()
      self.executable = f"ibstat"

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
      return sn.assert_eq(self.job.exitcode, 0)


@rfm.simple_test
class osu_bandwidth_test(OSUBenchmarkTestBase):
   descr = 'OSU bandwidth test'

   @run_after('compile')
   def set_test_flags(self):
      self.job.options = ['--time=02:00']
      #self.job.options.append('--array=1-2')

   @run_before('run')
   def prepare_run(self):
      self.job.launcher = getlauncher('mpiexec')()
      #self.executable = os.path.join(self.osu_dir,'osu_bw')
      self.executable = os.path.join(
            self.osu_binaries.stagedir,
            self.osu_binaries.build_prefix,
            'mpi', 'pt2pt', 'osu_bw'
        )
      self.executable_opts = ['-x', '100', '-i', '1000', '-m', '1048576:']
      #util.osext.run_command('ls')
      #print(self.job.nodelist)

   #@performance_function('GB/s')
   def bandwidth(self):
   #ireed: todo - find out how to fail after perf_function
      with open(str(self.stdout), mode='r') as fp:
         #fp = open(str(self.stdout),'r')
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
      #fail if test is slower that 95% of interconect rate
      lower = float(float(self.ib_stat.IB_RATE) * .95)
      # 100% interconnect speed is not possible, so fail
      upper = float(float(self.ib_stat.IB_RATE) * .99)
      #ireed: todo - add nodename(s) to error message
      gbs = self.bandwidth()
      return sn.assert_bounded(gbs,lower,upper,
         'Bandwidth performance failed: {}Gb/s is outside of error margin for {} Gb/s connection.'.format(gbs,self.ib_stat.IB_RATE))



