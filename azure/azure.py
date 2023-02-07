import sys
import os
import re
import json
import subprocess

#Author: Isayah Reed
#
#Purpose: Helper functions for getting info and data of Azure VM series
#

class Node:
#functions for getting info about the current node

   @staticmethod
   def getInfo():
   # returns full VM info, in a pretty json format
      cmd = "curl -s -H Metadata:true \"http://169.254.169.254/metadata/instance?api-version=2019-06-04\""
      #cmd = ['curl', '-H', 'Metadata:true http://169.254.169.254/metadata/instance?api-version=2019-06-04']
      results = os.popen(cmd).read()
      #results = subprocess.run(cmd, stdout=subprocess.PIPE)
      vm_data = json.loads(results)
      return json.dumps(vm_data, indent=2)


   @staticmethod
   def getVmSize():
   # returns the VM name (ex: Standard_ND40rs_v2)
      vm_data = json.loads(Node.getInfo())
      return vm_data['compute']['vmSize']



class Image:
#functions for getting info about a VM series

   #hard-code location of the Azure vm info file
   vmDataFile = '/shared/azure_nhc/reframe/azure_nhc/vm_info/azure_vms_dataset.json'

   @staticmethod
   def getCapabilities(vmSize):
      info = json.loads(Image.getInfo(vmSize))
      return json.dumps(info['capabilities'], indent=2)


   @staticmethod
   def getInfo(vmSize):
   # returns info about vmSize (ex: "Standard_D8ds_v4"), as a formatted json file

      #TODO: add option to set vmDataFile as env var
      f = open(Image.vmDataFile)
      vm_data = json.load(f)
      f.close()
      vm_series = vm_data[vmSize]
      return json.dumps(vm_series, indent=2)
