# Copyright 2016-2021 Swiss National Supercomputing Centre (CSCS/ETH Zurich)
# ReFrame Project Developers. See the top-level LICENSE file for details.
#
# SPDX-License-Identifier: BSD-3-Clause

import os
import json as js
import re
import reframe as rfm
import reframe.utility as util
import reframe.utility.sanity as sn
import reframe.utility.osext as osext
import sys

@rfm.simple_test
class PrintNodelist(rfm.RunOnlyRegressionTest):
   descr = 'Testing the _job_nodelist feature'

   valid_systems = ['*']
   valid_prog_environs = ['*']
   #store list of nodes in this file, because self.job.nodelist is unreliable
   nodelist_file ="reframe_nodelist.txt"


   @run_after('compile')
   def nodelist_compile(self):
      self.executable = f"hostname | sort > {self.nodelist_file}"
      print("After compile stage: ")
      print(self._job_nodelist)
      print(self.job.nodelist)

   @sanity_function
   def nodelist_sanity(self):
      print("Sanity stage: ")
      print(self._job_nodelist)
      print(self.job.nodelist)
      return sn.assert_true(True,"fail")


   @run_after('run')
   def nodelist_run(self):
      print("Run stage: ")
      print(self._job_nodelist)
      print(self.job.nodelist)


   @performance_function('%')
   def nodelist_performance(self):
      print("Performance stage: ")
      print(self._job_nodelist)
      print(self.job.nodelist)
      return sn.assert_true(True,"fail")
