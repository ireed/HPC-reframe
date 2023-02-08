import re
import reframe as rfm
import reframe.utility.sanity as sn
from reframe.core.exceptions import ReframeError
import reframe.utility.osext as osext
import sys

#Author: Isayah Reed
#
#Purpose: Ensures IB device naming begins with ib0
#


@rfm.simple_test
class IbNaming(rfm.RunOnlyRegressionTest):
   descr = 'Validates naming and ordering of IB cards'

   #valid_systems = ['*']
   valid_systems=['+ib']
   valid_prog_environs = ['*']
   error_msg=None

   @run_before('run')
   def prepare_run(self):
      #self.job.launcher = getlauncher('mpiexec')()
      #self.job.launcher = getlauncher('local')()
      self.job.options = ['--time=00:00:10']
      self.job.time_limit = 5
      self.executable = 'hostname; ifconfig -s'

   def check_ib_names(self,filename):
      if self.job.exitcode != 0:
         self.error_msg="ERROR: Job submission failed"
         return -1
      with open(str(filename), mode='r') as fp:
         data = fp.read()
      hostname = data.split('\n')[0]
      #separate output data from titles/header
      data = data.partition("Flg")[2].split()
      if_names = []
      #get list of only Iface entries - the 1st of 11 columns
      for i in range(len(data)):
         if i%11 == 0:
            if_names.append(data[i])
      r = re.compile("ib[0-9]")
      ib_names = list(filter(r.match, if_names))
      #print(ib_names)
      if len(ib_names) == 0:
         #TODO: should we check if IB cards are expected?
         self.error_msg="Error: {} has no IB cards".format(hostname)
         #TODO: should we fail if no IB cards?
         return -1
      if 'ib0' not in ib_names:
         self.error_msg="\tERROR: {} has no ib0. IB devices are - {}".format(hostname,ib_names)
         return -1
      return 0

   @sanity_function
   def validate_test(self):
      return sn.assert_eq(self.check_ib_names(self.stdout), 0, msg=self.error_msg)
      #return self.check_ib_names(self.stdout)
