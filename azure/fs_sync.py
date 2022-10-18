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
from reframe.core.exceptions import ReframeError
import reframe.utility.osext as osext
import sys

@rfm.simple_test
class FilesystemHomogeneity(rfm.RunOnlyRegressionTest):
   descr = 'Checks that all nodes have the same filesystems'

   valid_systems = ['*']
   valid_prog_environs = ['*']
   #store list of nodes in this file, because self.job.nodelist is unreliable
   nodelist_file ="reframe_nodelist.txt"
   # fail if any filesystem usage exceeds USAGE_LIMIT%
   USAGE_LIMIT = 90

   def get_nodelist(self,filename):
   # converts a file containing the jobs nodes into a list
      with osext.change_dir(self.stagedir):
         fp = open(filename,'r')
      nodes = fp.read()
      node_list = nodes.split('\n')
      del node_list[len(node_list)-1]
      return node_list


   @run_after('compile')
   def get_my_fs(self):
      cmd = "df -h"
      output = util.osext.run_command(cmd)
      if output.returncode != 0:
         print("Error: command df -h failed.\n")
         #exit(1)
         return False
      # convert df -h to a list
      output = output.stdout
      output = output.partition("Mounted on")[2].split()
      #print(self.current_system)
      self.executable = f"hostname | sort > {self.nodelist_file}"
      self.readonly_files = [self.nodelist_file]

   @sanity_function
   def assert_fs_mount(self):
      return sn.assert_true(self.check_fs_mount(),"FS mount checks fail")

   @run_before('compile')
   def set_test_flags(self):
      self.job.options = [
         '--ntasks=4',
         '--ntasks-per-node=1'
         ]
      #self.job.num_tasks = 2
      #self.job.num_tasks_per_node = 1
      #self.job.exclusive_access = True

#   @run_before('run')
#   def replace_launcher(self):
#      self.job.launcher = getlauncher('local')()


#   @performance_function('%')
#   def assert_fs_usage(self):
#      return sn.assert_true(self.check_fs_mount(),"FS usage checks fail")


   def check_fs_mount(self):
   # verify that each node has the same filesystem
      nodelist = self.get_nodelist(self.nodelist_file)
      df = []
      succ = True
      for node in nodelist:
         #cmd = "mpiexec -n 1 -host "+node+" df -h > ~/df."+node
         cmd = "mpiexec -n 1 -host "+node+" df -h"
         output = util.osext.run_command(cmd)
         #if output.returncode != 0:
         #   print("Error: Command df -h failed on node {}.\n".format(node))
         #   exit(1)

         # do this sequentially, so we know which output belongs to each node
         util.osext.run_command("wait")
         df.append(output.stdout)

      print("Checking if filesystems exceed {}% usage ...".format(self.USAGE_LIMIT))
      for i in range(0,len(df) ):
         succ = succ & self.check_fs_used(df[i],nodelist[i])

      print("Checking if nodes have same filesystems ...")
      if len(df) == 1:
         return succ
      for i in range(0,len(df)-1 ):
         if self.compare_fs(df[i],df[i+1]) is False:
            print("\tError: nodes {} and {} do not have the same filesystem".format(nodelist[i],nodelist[i+1]))
            succ = False
      if self.compare_fs(df[0],df[len(df)-1]) is False:
         print("\tError: nodes {} and {} do not have the same filesystem".format(nodelist[i],nodelist[i+1]))
         succ = False

      return succ

   #@run_after('run')
   def check_fs_used(self,df,node):
      # check if any filesystems exceed USAGE_ LIMIT percent
      # input 'df' is the std output from $> df -h
      # returns the df output, without the headers (i.e Size, Avail, etc)

      succ = True
      # convert df -h to a list
      df = df.partition("Mounted on")[2].split()
      # iterate through the 'Use%' (column #5 of 6) in df -h list
      for i in range(0,int(len(df)/6) ):
         usage = df[(6*i)+4]
         mnt = df[(6*i)+5]
         usage = int(usage.replace('%',''))
         # fail if Use% is more than out pre-set limit
         if usage >= self.USAGE_LIMIT:
            #raise ReframeError('Error: filesystem {} usage is too high, {}%\n'.format(mnt,usage) )
         # or, just print a warning and continue
            print('\tWarning: filesystem {} usage is too high, {}% on node {}\n'.format(mnt,usage,node) )
            succ = False
      return succ


   def compare_fs(self,df1,df2):
      # remove headers from df output
      df1 = df1.partition("Mounted on")[2].split()
      df2 = df2.partition("Mounted on")[2].split()

      if( int(len(df1)/6) != int(len(df2)/6) ):
      #if num rows in df outputs are not equal, they cant have the same FS
         return False

      for i in range(0,int(len(df1)/6) ):
      # iterate through the 'Mounted On' (column #6 of 6) in df -h list
         mnt1 = df1[(6*i)+5]
         mnt2 = df2[(6*i)+5]
         if mnt1 != mnt2:
         # nodes have different filesystems
            return False
      return True


