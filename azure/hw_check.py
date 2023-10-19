import reframe as rfm
import reframe.utility.sanity as sn
import reframe.core.config as cfg
import reframe.utility.osext as osext
import reframe.utility as util
import os
from reframe.core.backends import getlauncher
import json

#Author: Isayah Reed
#
#Purpose: Basic device checks (lspci, count network devices, etc)
#
#Example run command: $> ./bin/reframe -C config.py -c hw_check.py -r --system azure:nca100v4 -S local=1


class HwCheckTestBase(rfm.RunOnlyRegressionTest):

   descr = 'Base class of HW check tests'
   valid_systems = ['*']
   valid_prog_environs = ['*']
   num_tasks = 1
   num_tasks_per_node = 1
   # functional tests dont require exclusive access
   exclusive_access = False
   vm_info_file = 'azure/config/azure_vms_dataset.json'
   #prerun_cmds = ['echo START']
   #postrun_cmds = ['echo FINISH']

   @sanity_function
   def validate_test(self):
      return sn.assert_eq(self.job.exitcode, 0)




@rfm.simple_test
class lscpu(HwCheckTestBase):
   descr = 'lscpu'
   executable = 'lscpu'
   vm_name = ''
   vm_info = ''

   @run_before('run')
   def set_test_flags(self):
      self.job.options = ['--time=00:20']
      #self.job.launcher = getlauncher('mpiexec')()
      self.job.launcher = getlauncher('local')()
      self.executable = 'lscpu'


   @run_after('compile')
   def get_vm_name(self):
      #cmd = "curl -s -H Metadata:true --noproxy '*' 'http://169.254.169.254/metadata/instance?api-version=2020-06-01' | jq -r '.compute.vmSize'"
      cmd = "curl -s -H Metadata:true --noproxy '*' 'http://169.254.169.254/metadata/instance?api-version=2020-06-01'"
      output = util.osext.run_command(cmd)
      if output.returncode != 0:
         print("Error: could not get VM name.\n")
         return False
      tmp = json.loads(output.stdout)
      self.vm_name = tmp['compute']['vmSize']
      return True


   def parse_output(self,filename):
   # parse the lscpu output into a dictionary of key-value pairs
      with open(str(filename), mode='r') as fp:
         data = fp.read()
      lines = data.replace('\n',': ').split(': ')
      # remove leading white spaces
      for i in range(0,len(lines)):
         lines[i] = lines[i].lstrip(' ')

      pairs = dict(zip(*[iter(lines)]*2))
      return pairs


   def check_cpu_speed(self,pairs):
   # checks cpu MHz from lscpu; input is lscpu results, as a dictionary
      cpu_speed = pairs.get('CPU MHz')
      #TODO: what is the expected speed/range for each VM?
      return True


   def check_num_cpus_online(self,pairs):
   # checks if all cpus are online
      num_cpus = int(pairs.get('CPU(s)'))
      num_cpus_online = pairs.get('On-line CPU(s) list')
      # 'online cpu' output format is, for example, '0-8'; need to get the '8'
      # (note: this will probably fail on a single-core system)
      num_cpus_online = int(num_cpus_online.split('-')[1])
      num_cpus_online = num_cpus_online+1
      if num_cpus != num_cpus_online:
         print("Num CPUs online does not match total num CPUs available")
         return False
      return True

   #TODO:
   #def check_numa(self):
      # verifies number of numa nodes, and if configured properly


   @sanity_function
   def validate_test(self):
      output_pairs = self.parse_output(self.stdout)
      if self.check_cpu_speed(output_pairs) is not True:
         return False
      if self.check_num_cpus_online(output_pairs) is not True:
         return False
      return sn.assert_eq(self.job.exitcode, 0, "lscpu failed")
