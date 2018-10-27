"""
Copyright Eviatar Bach (eviatarbach@protonmail.com) 2015–2018.

Licensed under the MIT License. See license text at
https://opensource.org/licenses/MIT.

Part of simulation_runner, https://github.com/eviatarbach/simulation_runner.
"""
from namers import SequentialNamer
from dispatchers import PythonSubprocessDispatcher, DRMAADispatcher
from templates import PythonFormatTemplate, MakoTemplate

import itertools
import time
import operator
import datetime
from functools import reduce


def run_sweep(command, config_paths, sweep_id=None, template_paths=None,
              template_texts=None, fixed_parameters={}, sweep_parameters={},
              naming=SequentialNamer(), dispatcher=PythonSubprocessDispatcher,
              template_engine=PythonFormatTemplate, run=True, delay=False,
              wait=False, verbose=True, param_array=True, serial=False):
    r"""
    Run parameter sweeps.

    This function runs the program with the Cartesian product of the parameter
    ranges.

    EXAMPLES:
    >>> run_sweep('cat {sim_id}.txt', ['{sim_id}.txt'],
    ...           template_texts=['Hello ${x*10}\n'],
    ...           sweep_parameters={'x': [1, 2, 3]}, verbose=False,
    ...           template_engine=MakoTemplate)
    Hello 10
    Hello 20
    Hello 30

    >>> run_sweep('cat {sim_id}.txt', ['{sim_id}.txt'],
    ...           template_texts=['Hello {x:.2f}\n'],
    ...           sweep_parameters={'x': [1/3, 2/3, 3/3]}, verbose=False)
    Hello 0.33
    Hello 0.67
    Hello 1.00

    >>> run_sweep('cat {sim_id}_1.txt {sim_id}_2.txt',
    ...           ['{sim_id}_1.txt', '{sim_id}_2.txt'],
    ...           template_texts=['Hello {x:.2f}\n', 'Hello again {y}\n'],
    ...           sweep_parameters={'x': [1/3, 2/3, 3/3], 'y': [4]},
    ...           verbose=False)
    Hello 0.33
    Hello again 4
    Hello 0.67
    Hello again 4
    Hello 1.00
    Hello again 4

    """
    if (((template_paths is None) and (template_texts is None))
            or (not (template_paths is None)
                and not (template_texts is None))):
        raise ValueError('Exactly one of `template_paths` or `template_texts` '
                         'must be provided.')

    if (isinstance(config_paths, str) or isinstance(template_paths, str)
            or isinstance(template_texts, str)):
        raise TypeError('`config_paths` and `template_paths` or'
                        '`template_texts` must be a list.')

    if not sweep_id:
        current_time = datetime.datetime.now()
        sweep_id = current_time.strftime('%Y-%m-%dT%H:%M:%S')

    if template_paths:
        config = template_engine(paths=template_paths)
    else:
        config = template_engine(texts=template_texts)

    params = fixed_parameters.copy()
    keys = list(sweep_parameters.keys())
    values = list(sweep_parameters.values())
    lengths = [len(value) for value in values]

    if sweep_parameters:
        product = itertools.product(*values)
    else:
        product = [params]

    naming.start(length=reduce(operator.mul, lengths, 1))

    sim_ids = []

    if run:
        session = dispatcher()

    for param_set in product:
        sweep_params = params.copy()
        if keys:
            for index, value in enumerate(param_set):
                sweep_params[keys[index]] = value

        sim_id = naming.next(keys, sweep_params.values())
        sim_ids.append(sim_id)

        rendered = config.render(sweep_params)
        for config_rendered, config_path in zip(rendered, config_paths):
            with open(config_path.format(sim_id=sim_id), 'wb') as config_file:
                config_file.write(config_rendered.encode('utf-8', 'replace'))
        if run:
            if verbose:
                print("Running simulation {sim_id} with "
                      "parameters:".format(sim_id=sim_id))
                print('\n'.join('{key}: {param}'.format(key=key,
                                                        param=param)
                                for key, param in zip(keys, param_set)))
            session.dispatch(command.format(sim_id=sim_id), serial)
            if delay:
                time.sleep(delay)

    if wait and run:
        session.wait_all()

    if param_array:
        import xarray
        import numpy

        sim_ids_array = xarray.DataArray(numpy.reshape(numpy.array(sim_ids),
                                                       lengths),
                                         coords=values, dims=keys)

        sim_ids_filename = 'sim_ids_{sweep_id}.nc'.format(sweep_id=sweep_id)

        sim_ids_array.to_netcdf(sim_ids_filename)

        return sim_ids_array
