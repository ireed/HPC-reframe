
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

#Author: Isayah Reed
#
#Purpose: Downloads NCCL and NCCL test repo, builds them, then runs various
#   NCCL tests on multiple gpus.
#
#Example run command: $> ./bin/reframe -C azure_nhc/config/azure_ubuntu_20.py -c nccl-tests.py -r --system nvads_a10_v5:gpu

class fetch_nccl(rfm.RunOnlyRegressionTest):
   descr = 'Fetch NCCL'
   #valid_systems = ['*']
   #valid_prog_environs = ['gnu']
   executable = 'wget'
   executable_opts = [
      f'https://github.com/NVIDIA/nccl/archive/refs/heads/master.zip; mv master.zip nccl.zip'
   ]
   local = True

   @sanity_function
   def validate_download(self):
      return sn.assert_eq(self.job.exitcode, 0)

class fetch_nccl_tests(rfm.RunOnlyRegressionTest):
   descr = 'Fetch NCCL tests'
   executable = 'wget'
   executable_opts = [
      f'https://github.com/NVIDIA/nccl-tests/archive/refs/heads/master.zip; mv master.zip nccl_tests.zip'
   ]
   local = True

   @sanity_function
   def validate_download(self):
      return sn.assert_eq(self.job.exitcode, 0)


class build_nccl(rfm.CompileOnlyRegressionTest):
   descr = 'Build NCCL'
   build_system = 'Make'
   build_prefix = variable(str)
   nccl_zip = fixture(fetch_nccl, scope='session')

   @run_before('compile')
   def prepare_build(self):
      #tarball = f'master.zip'
      tarball = f'nccl.zip'
      self.build_prefix = f'nccl-master'

      fullpath = os.path.join(self.nccl_zip.stagedir, tarball)
      self.prebuild_cmds = [
         f'cp {fullpath} {self.stagedir}',
         f'unzip {tarball}',
         f'cd {self.build_prefix}'
      ]
      #arch for A100; change for other GPUs
      ARCH='compute_80'
      CODE='sm_80'
      gencode="\"-gencode=arch={},code={}\"".format(ARCH,CODE)
      # make -j src.build NVCC_GENCODE="-gencode=arch=compute_70,code=sm_70"
      self.build_system.max_concurrency=8
      self.build_system.options=['src.build', "NVCC_GENCODE={}".format(gencode)]

   @sanity_function
   def validate_build(self):
        # If compilation fails, the test would fail in any case, so nothing to
        # further validate here.
      return True

class build_nccl_tests(rfm.CompileOnlyRegressionTest):
   descr = 'Build NCCL tests'
   build_system = 'Make'
   build_prefix = variable(str)
   nccl_dir = fixture(build_nccl, scope='environment')
   nccl_tests_zip = fixture(fetch_nccl_tests, scope='session')

   @run_before('compile')
   def prepare_build(self):
      #tarball = f'master.zip'
      tarball = f'nccl_tests.zip'
      self.build_prefix = f'nccl-tests-master'

      fullpath = os.path.join(self.nccl_tests_zip.stagedir, tarball)
      self.prebuild_cmds = [
         f'cp {fullpath} {self.stagedir}',
         f'unzip {tarball}',
         f'cd {self.build_prefix}'
      ]

      NCCL_HOME = self.nccl_dir.stagedir
      #find nvcc
      CUDA_HOME = '/usr/local/cuda'
      output = util.osext.run_command('ls {}/bin/nvcc'.format(CUDA_HOME))
      if output.returncode != 0:
         output = util.osext.run_command('which nvcc')
         if output.returncode != 0:
            print("Cannot load cannot find nvcc.\n")
            return False
         else:
            CUDA_HOME = output.stdout[:9] #remove '/bin/nvcc'

      #find MPI
      MPI='MPI=0'
      MPI_HOME='/opt/openmpi'
      output = util.osext.run_command('which mpicc')
      if output.returncode != 0:
         #using impi because ompi has different paths/versions for
         #  different OS flavors
         output = util.osext.run_command('module load mpi/impi')
         output = util.osext.run_command('module load mpi/hpcx')
         if output.returncode != 0:
            print("Cannot load modules for MPI.\n")
            MPI='MPI=1'
            MPI_HOME='_'
         else:
            output = util.osext.run_command('which mpicc')
            MPI_HOME = output.stdout[:10] #remove '/bin/mpicc'
      else:
         MPI_HOME = output.stdout[:10] #remove '/bin/mpicc'


      #build command: $> make MPI=1 MPI_HOME=/path/to/mpi
      #     CUDA_HOME=/path/to/cuda NCCL_HOME=/path/to/nccl
      self.build_system.max_concurrency = 8
      self.build_system.options=[MPI, "MPI_HOME="+MPI_HOME, "CUDA_HOME="+CUDA_HOME, "NCCL_HOME="+NCCL_HOME]
      #self.build_system.max_concurrency = "{} MPI_HOME={} CUDA_HOME={} NCCL_HOME={}".format(MPI,MPI_HOME,CUDA_HOME,NCCL_HOME)
      # tests are located in $NCCL_HOME/build

   @sanity_function
   def validate_build(self):
      output = util.osext.run_command('echo $?')
      if output.returncode != 0:
         return False
      return True





class NCCLTestBase(rfm.RunOnlyRegressionTest):
   '''Base class of NCCL tests'''

   valid_systems = ['*']
   valid_prog_environs = ['*']
   num_tasks = 1
   num_tasks_per_node = 1
   exclusive_access = True
   nccl_test = fixture(build_nccl_tests, scope='environment')

   @sanity_function
   def validate_test(self):
      return sn.assert_eq(self.job.exitcode, 0)




@rfm.simple_test
class nccl_alltoall_test(NCCLTestBase):
   descr = 'NCCL All-to-All test'

   @run_after('compile')
   def set_test_flags(self):
      self.job.options = ['--time=02:00']
      #self.job.options.append('--array=1-2')

   @run_before('run')
   def prepare_run(self):
      # $> <nccl_test_dir>/build/alltoall_perf -b 8 -e 128M -f 2 -g 2
      nccl_test_dir = os.path.join(self.nccl_test.stagedir,
            self.nccl_test.build_prefix, 'build' )
      self.executable = os.path.join(nccl_test_dir, 'alltoall')
      self.executable_opts = ['-b 8', '-e 128M', '-f 2', '-g 2']

   #@performance_function('GB/s')
   def get_bandwidth(self,filename):
      with open(str(filename), mode='r') as fp:
         data = fp.read()
      print(data)
      return 0
      #data_list = data.split('\n')
      #bw = [s for s in data_list if '33554432' in s]
      #bw = re.split(' +', bw[0])
      #gbs = float(float(bw[1]) * 8 / 1000)
      #gbs = float(f'{gbs:.2f}')
      #print(gbs)
      #return gbs

   @sanity_function
   def validate_test(self):
   #ireed: todo - find out expected b/w outputs
      gbs = self.get_bandwidth(self.stdout)
      sn.assert_ne(self.job.exitcode, 0, "Error NCCL test failed")

