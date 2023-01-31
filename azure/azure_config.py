
#Author: Isayah Reed
#
#Purpose: Experimental config file for Azure VMs
#
# 


site_configuration = {
    'systems': [
        {
            'name': 'azure',
            'descr': 'Azure VM',
            'vm_data_file': 'azure_nhc/vm_info/azure_vms_dataset.json',
            'hostnames': ['*'],
            'modules_system': 'tmod4',
            'partitions': [
                {
                    'name': 'hbv2',
                    'descr': 'HB120rs_v2',
                    'scheduler': 'slurm',
                    'launcher': 'srun',
                    'max_jobs': 100,
                    #ireed: this is actually not needed ... at the moment
                    'access': ['-p hbv2'],
                    'environs': ['gnu-azhpc'],
                    'prepare_cmds': ['source /etc/profile.d/modules.sh'],
                    'features': ['ib', 'mpi'],
                    'extras': {'vm_size': 'HB120rs_v2', 'gpu_arch': 'a100' }
                },
                {
                    'name': 'nca100v4',
                    'descr': 'ncads_a100_v4',
                    'scheduler': 'slurm',
                    'launcher': 'srun',
                    'max_jobs': 100,
                    'access': ['-p nca100v4'],
                    'environs': ['gnu-azhpc'],
                    'prepare_cmds': ['source /etc/profile.d/modules.sh'],
                    'features': ['ib', 'gpu', 'cuda', 'mpi'],
                    'extras': {'vm_size': 'ncads_a100_v4', 'gpu_arch': 'a100' }
                },
                {
                    'name': 'ndv2',
                    'descr': 'ndrs_v2',
                    'scheduler': 'slurm',
                    'launcher': 'srun',
                    'max_jobs': 100,
                    'access': ['-p ndv2'],
                    'environs': ['gnu-azhpc'],
                    'prepare_cmds': ['source /etc/profile.d/modules.sh'],
                    'features': ['gpu', 'cuda', 'mpi'],
                    'extras': {'vm_size': 'ndrs_v2', 'gpu_arch': 'a100' }
                }
            ]
        },
        {
            'name': 'generic',
            'descr': 'Generic example system',
            'hostnames': ['.*'],
            'partitions': [
                {
                    'name': 'default',
                    'scheduler': 'local',
                    'launcher': 'local',
                    'environs': ['builtin'],
                    'prepare_cmds': ['source /etc/profile.d/modules.sh']
                }
            ]
        }
    ],

    'environments': [
        {
            'name': 'builtin',
            'cc': 'cc',
            'cxx': '',
            'ftn': ''
        },
        {
            'name': 'gnu-azhpc',
            'modules': ['mpi/hpcx'],
            'cc': 'gcc',
            'cxx': 'g++',
            'ftn': 'gfortran'
        },
        {
            'name': 'gnu',
            'cc': 'gcc',
            'cxx': 'g++',
            'ftn': 'gfortran'
        },
    ],
    'logging': [
        {
            'handlers': [
                {
                    'type': 'stream',
                    'name': 'stdout',
                    'level': 'info',
                    'format': '%(message)s'
                },
                {
                    'type': 'file',
                    'level': 'debug',
                    'format': '[%(asctime)s] %(levelname)s: %(check_info)s: %(message)s', 
                    'append': False
                }
            ],
            'handlers_perflog': [
                {
                    'type': 'filelog',
                    'prefix': '%(check_system)s/%(check_partition)s',
                    'level': 'info',
                    'format': (
                        '%(check_job_completion_time)s|reframe %(version)s|'
                        '%(check_info)s|jobid=%(check_jobid)s|'
                        '%(check_perf_var)s=%(check_perf_value)s|'
                        'ref=%(check_perf_ref)s '
                        '(l=%(check_perf_lower_thres)s, '
                        'u=%(check_perf_upper_thres)s)|'
                        '%(check_perf_unit)s'
                    ),
                    'append': True
                }
            ]
        }
    ],
}
