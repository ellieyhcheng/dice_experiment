# import matplotlib.pyplot as plt
import os 
import argparse
import subprocess
import json
import re
import matplotlib.pyplot as plt
from string import Template
from enum import Enum
import time

class Fields(str, Enum):
  TIME = 'time'
  SIZE = 'size'
  CALLS = 'calls'
  FLIPS = 'flips'
  PARAMS = 'params'
  DISTINCT = 'distinct'

  def __str__(self):
    return self.value

class Modes(str, Enum):
  NOOPT = 'no opts'
  DET = 'det + be'
  FH = 'fh + det + be'
  FHCT = 'fh + ct + det + be'
  SBK = 'sbk + det + be'
  SBKFH = 'sbk + fh + det + be'
  SBKFHCT = 'sbk + fh + ct + det + be'

  EA = 'ea + det + be'
  EAFH = 'ea + fh + det + be'
  EAFHCT = 'ea + fh + ct + det + be'
  EASBK = 'ea + sbk + det + be'
  EASBKFH = 'eg + sbk + fh + det + be'
  EASBKFHCT = 'eg + sbk + fh + ct + det + be'

  def __str__(self):
    return self.name

  @staticmethod
  def from_string(s):
    try:
      return Modes[s]
    except KeyError:
      raise ValueError()

  @staticmethod
  def to_column(m):
    mapping = {
      Modes.NOOPT: 'No Opt',
      Modes.DET: 'Det',
      Modes.FH: 'FH',
      Modes.FHCT: 'FHCT',
      Modes.SBK: 'SBK',
      Modes.SBKFH: 'SBK+FH',
      Modes.SBKFHCT: 'SBK+FHCT',
      Modes.EA: 'Ea',
      Modes.EAFH: 'Ea+FH',
      Modes.EAFHCT: 'Ea+FHCT',
      Modes.EASBK: 'Ea+SBK',
      Modes.EASBKFH: 'Ea+SBK+FH',
      Modes.EASBKFHCT: 'Ea+SBK+FHCT'
    }
    
    return mapping[m]

def get_mode_cmd(mode):
  if mode == Modes.NOOPT:
    return []
  if mode == Modes.DET:
    return ['-determinism']
  if mode == Modes.FH:
    return ['-determinism', '-local-hoisting', '-branch-elimination']
  if mode == Modes.FHCT:
    return ['-determinism', '-global-hoisting', '-branch-elimination']
  if mode == Modes.SBK:
    return ['-determinism', '-sbk-encoding', '-branch-elimination']
  if mode == Modes.SBKFH:
    return ['-determinism', '-local-hoisting', '-sbk-encoding', '-branch-elimination']
  if mode == Modes.SBKFHCT:
    return ['-determinism', '-global-hoisting', '-sbk-encoding', '-branch-elimination']
  if mode == Modes.EA:
    return ['-eager-eval', '-determinism', '-branch-elimination']
  if mode == Modes.EAFH:
    return ['-eager-eval', '-local-hoisting', '-determinism', '-branch-elimination']
  if mode == Modes.EAFHCT:
    return ['-eager-eval', '-global-hoisting', '-determinism', '-branch-elimination']
  if mode == Modes.EASBK:
    return ['-eager-eval', '-sbk-encoding', '-determinism', '-branch-elimination']
  if mode == Modes.EASBKFH:
    return ['-eager-eval', '-sbk-encoding', '-local-hoisting', '-determinism', '-branch-elimination']
  if mode == Modes.EASBKFHCT:
    return ['-eager-eval', '-sbk-encoding', '-global-hoisting', '-determinism', '-branch-elimination']
  
  return None

def run(file, dice_path, timeout, fields, modes):
  print('========================================')

  print('File:', file)

  results = {f:{m:None for m in modes} for f in fields}

  if Fields.TIME in fields:
    print('Measuring time elapsed...')
    for mode in modes:
      cmd = get_mode_cmd(mode)
      if cmd is None:
        print('UNKNOWN MODE')
        continue

      print('Mode:', mode)

      try:
        t1 = time.time()
        p = subprocess.Popen([dice_path, file, '-skip-table'] + cmd, 
          stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        t2 = time.time()
        results[Fields.TIME][mode] = round(t2 - t1, 4)

      except subprocess.TimeoutExpired:
        print('TIMEOUT')
        p.terminate()

    print()
  
  if Fields.SIZE in fields or Fields.CALLS or Fields.FLIPS in fields \
    or Fields.PARAMS in fields or Fields.DISTINCT in fields:
    print('Measuring BDD size, number of recursive calls, and/or number of calls...')
    cmd = [dice_path, file, '-skip-table']
    if Fields.SIZE in fields:
      cmd.append('-show-size')
    if Fields.CALLS in fields:
      cmd.append('-num-recursive-calls')

    if not Fields.SIZE in fields and not Fields.CALLS in fields:
      cmd.append('-no-compile')
    
    if Fields.FLIPS in fields:
      cmd.append('-show-flip-count')
    if Fields.PARAMS in fields:
      cmd.append('-show-params')

    for mode in modes:
      mode_cmd = get_mode_cmd(mode)
      if mode_cmd is None:
        print('UNKNOWN MODE')
        continue

      print('Mode:', mode)

      try:
        p = subprocess.Popen(cmd + mode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
        out, err = p.communicate(timeout=timeout)
        output = out.decode('utf-8')
        call_pattern = re.compile('================\[ Number of recursive calls \]================\s(\d+.?\d*)')
        size_pattern = re.compile('================\[ Final compiled BDD size \]================\s(\d+.?\d*)')
        flip_pattern = re.compile('================\[ Number of flips \]================\s(\d+.?\d*)')
        param_pattern = re.compile('================\[ Number of Parameters \]================\s(\d+.?\d*)')
        distinct_pattern = re.compile('================\[ Number of Distinct Parameters \]================\s(\d+.?\d*)')
        
        call_matches = call_pattern.search(output)
        size_matches = size_pattern.search(output)
        flip_matches = flip_pattern.search(output)
        param_matches = param_pattern.search(output)
        distinct_matches = distinct_pattern.search(output)

        if call_matches:
          if not Fields.CALLS in results:
            results[Fields.CALLS] = {}
          results[Fields.CALLS][mode] = int(float(call_matches.group(1)))
        
        if size_matches:
          if not Fields.SIZE in results:
            results[Fields.SIZE] = {}
          results[Fields.SIZE][mode] = int(float(size_matches.group(1)))

        if flip_matches:
          if not Fields.FLIPS in results:
            results[Fields.FLIPS] = {}
          results[Fields.FLIPS][mode] = int(float(flip_matches.group(1)))

        if param_matches:
          if not Fields.PARAMS in results:
            results[Fields.PARAMS] = {}
          results[Fields.PARAMS][mode] = int(float(param_matches.group(1)))

        if distinct_matches:
          if not Fields.DISTINCT in results:
            results[Fields.DISTINCT] = {}
          results[Fields.DISTINCT][mode] = int(float(distinct_matches.group(1)))

        if not call_matches and not size_matches and not flip_matches and not param_matches:
          if not Fields.CALLS in results:
            results[Fields.CALLS] = {}
          if not Fields.SIZE in results:
            results[Fields.SIZE] = {}
          if not Fields.FLIPS in results:
            results[Fields.FLIPS] = {}
          if not Fields.PARAMS in results:
            results[Fields.PARAMS] = {}
          if not Fields.DISTINCT in results:
            results[Fields.DISTINCT] = {}
          results[Fields.SIZE][mode] = -1
          results[Fields.CALLS][mode] = -1
          results[Fields.FLIPS][mode] = -1
          results[Fields.PARAMS][mode] = -1
          results[Fields.DISTINCT][mode] = -1
          print('ERROR:')
          print(output)

      except subprocess.TimeoutExpired:
        print('TIMEOUT')
        p.terminate()

    print()

  return results

def problog(file, timeout):
  print('========================================')

  print('File:', file)

  print('Measuring time elapsed...')
  try:
    t1 = time.time()
    p = subprocess.Popen(['problog', file], 
      stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    out, err = p.communicate(timeout=timeout)
    t2 = time.time()
    result = round(t2 - t1, 4)
    print()
    return result

  except subprocess.TimeoutExpired:
    print('TIMEOUT')
    p.terminate()
    print()
    return None

def cnf(file, dice_path, timeout, results):
  print('========================================')

  print('File:', file)

  modes = [Modes.DET, Modes.FH]

  print('Measuring BDD size, number of recursive calls, and/or number of calls...')
  cmd = [dice_path, file, '-cnf', '-show-cnf-decisions']
  for mode in modes:
    if Fields.SIZE in results:
      if results[Fields.SIZE][mode] is not None and results[Fields.SIZE][mode] != -1:
        print('Skip')
        continue

    mode_cmd = get_mode_cmd(mode)
    if mode_cmd is None:
      print('UNKNOWN MODE')
      continue

    print('Mode:', mode)

    try:
      p = subprocess.Popen(cmd + mode_cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
      out, err = p.communicate(timeout=timeout)
      output = out.decode('utf-8')
      dec_pattern = re.compile('================\[ Average CNF decisions \]================\s(\d+.?\d*)')
      dec_matches = dec_pattern.search(output)

      if dec_matches:
        if not Fields.SIZE in results:
          results[Fields.SIZE] = {}
        results[Fields.SIZE][mode] = int(float(dec_matches.group(1)))
      
      
      if not dec_matches :
        if not Fields.SIZE in results:
          results[Fields.SIZE] = {}
        results[Fields.SIZE][mode] = -1
        print('ERROR:')
        print(output)

    except subprocess.TimeoutExpired:
      print('TIMEOUT')
      p.terminate()

  print()
  
  return results

def main():
  parser = argparse.ArgumentParser(description="Test harness for Dice experiments.")
  parser.add_argument('-i', '--dir', type=str, nargs=1, help='directory of experiment Dice files')
  parser.add_argument('-d', '--dice', type=str, nargs=1, help='path to Dice')
  parser.add_argument('-o', '--out', type=str, nargs='?', const='results.json', default='results.json', help='path to output file. Defaults to results.json')
  parser.add_argument('--table', action='store_true', help='prints data from output file as Latex table')
  parser.add_argument('--plot', type=str, nargs='?', const='cactus_plot.png', help='generate cactus plot. specify filename or default to cactus_plot.png')
  parser.add_argument('--columns', nargs='+', type=Modes.from_string, choices=list(Modes), help='select modes to include in the table or plot')

  parser.add_argument('--timeout', type=int, nargs=1, help='sets timeout in seconds')
  parser.add_argument('-t', '--time', dest='fields', action='append_const', const=Fields.TIME, help='record time elapsed')
  parser.add_argument('-s', '--size', dest='fields', action='append_const', const=Fields.SIZE, help='record BDD size')
  parser.add_argument('-c', '--calls', dest='fields', action='append_const', const=Fields.CALLS, help='record number of recursive calls')
  parser.add_argument('-f', '--flips', dest='fields', action='append_const', const=Fields.FLIPS, help='record number of flips')
  parser.add_argument('-p', '--params', dest='fields', action='append_const', const=Fields.PARAMS, help='record number of parameters')
  parser.add_argument('-dp', '--distinct', dest='fields', action='append_const', const=Fields.DISTINCT, help='record number of distinct parameters')

  parser.add_argument('--problog', action='store_true', help='runs Problog programs')
  parser.add_argument('--cnf', action='store_true', help="runs Dice with sharpSAT")

  parser.add_argument('--modes', nargs='*', type=Modes.from_string, choices=list(Modes), help='select modes to run over')

  args = parser.parse_args()
  
  out = args.out

  old_data = {
    'timeouts': {m:None for m in Modes},
    'results': {}
  }

  if os.path.exists(out):
    with open(out, 'r') as f:
      old_data = json.load(f)

  if args.problog:
    files = args.dir[0]
    results = {}
    if not os.path.isdir(files):
      print('Invalid directory specified:', files)
      exit(2)
    else:
      print('Experiment dir:', files)
      print('Output file:', out)

      if args.timeout:
        print('Timeout:', args.timeout[0])
        timeout = args.timeout[0]
      else:
        timeout = None

      print()

      for filename in os.listdir(files):
        file = os.path.join(files, filename)
        if os.path.isfile(file) and os.path.splitext(file)[-1].lower() == '.pl':
          results[filename] = problog(file, timeout)

      print()
      
    with open('problog_results.json', 'w') as f:
      json.dump(results, f, indent=4)

  elif args.cnf:
    files = args.dir[0]
    out = 'cnf_results.json'
    if os.path.exists(out):
      with open(out) as f:
        results = json.load(f)
    else:
      results = {}
    if not os.path.isdir(files):
      print('Invalid directory specified:', files)
      exit(2)
    else:
      print('Experiment dir:', files)
      print('Output file:', out)

      if args.timeout:
        print('Timeout:', args.timeout[0])
        timeout = args.timeout[0]
      else:
        timeout = None

      if args.dice:
        dice_path = args.dice[0]
      else:
        dice_path = './'

      print()

      for filename in os.listdir(files):
        file = os.path.join(files, filename)
        if os.path.isfile(file) and os.path.splitext(file)[-1].lower() == '.dice':
          if filename in results:
            file_results = results[filename]
          else:
            file_results = {}
          if not Fields.SIZE in file_results:
            modes = [Modes.DET, Modes.FH]
            file_results[Fields.SIZE] = {m:None for m in modes}
          results[filename] = cnf(file, dice_path, timeout, file_results)

      print()
      
    with open(out, 'w') as f:
      json.dump(results, f, indent=4)

  elif args.dir:
    files = args.dir[0]
    if not os.path.isdir(files):
      print('Invalid directory specified:', files)
      exit(2)
    else:
      print('Experiment dir:', files)
      print('Output file:', out)

      if args.timeout:
        print('Timeout:', args.timeout[0])
        timeout = args.timeout[0]
      else:
        timeout = None

      fields = args.fields or []

      if args.dice:
        dice_path = args.dice[0]
      else:
        dice_path = './'

      if args.modes:
        modes = args.modes
      else:
        print('Please select at least one mode')
        exit(2)

      for m in modes:
        old_data['timeouts'][m] = timeout

      print()

      results = {}

      for filename in os.listdir(files):
        file = os.path.join(files, filename)
        if os.path.isfile(file) and os.path.splitext(file)[-1].lower() == '.dice':
          results[filename] = run(file, dice_path, timeout, fields, modes)

      print()

    

    old_results = old_data['results']
      
    for filename in results.keys():
      if filename in old_results:
        for field in results[filename]:
          if not field in old_results[filename]:
            old_results[filename][field] = {}
          for mode in results[filename][field]:
            old_results[filename][field][mode] = results[filename][field][mode]
      else:
        old_results[filename] = results[filename]

    old_data['results'] = old_results
      
    with open(out, 'w') as f:
      json.dump(old_data, f, indent=4)

  if args.table:
    print('========= Table =========')

    if not old_data['results']:
      print('ERRORS: No results to use')
      exit(2)
    
    old_results = old_data['results']

    table = Template("""\\begin{table}[h]
\\caption{$caption}
\\begin{tabular}{$alignments}
\\toprule
Benchmarks & $columns \\\\
\\midrule
$rows
\\bottomrule
\\end{tabular}
\\end{table}""")

    for f in Fields:
      modes = args.columns or Modes
      columns = " & ".join(map(Modes.to_column, modes))
      alignments = 'l' + 'r' * len(modes)
      rows = []
      max_col_vals = {}

      make_table = True
      for filename in old_results.keys():
        if not f in old_results[filename]:
          make_table = False
      
      if make_table:
        for filename in sorted(old_results.keys()):
          cols = []
        
          for m in modes:
            if m in old_results[filename][f] and old_results[filename][f][m]:
              cols.append(old_results[filename][f][m])

          max_col_vals[filename] = min(cols) if cols else None

        for filename in sorted(old_results.keys()):
          cols = ['\\textsc{' + filename.split('.')[0].replace('_', '\_') + '}']
        
          for m in modes:
            if f == Fields.TIME:
              if m in old_results[filename][f] and old_results[filename][f][m] and max_col_vals[filename]:
                if old_results[filename][f][m] == -1:
                  cols.append('*')
                else:
                  if round(old_results[filename][f][m], 2) == round(max_col_vals[filename], 2):
                    cols.append('\\textbf{%.2f}' % old_results[filename][f][m])
                  else:
                    cols.append('%.2f' % old_results[filename][f][m])
              else:
                cols.append('-')
            else:
              if m in old_results[filename][f] and old_results[filename][f][m] and max_col_vals[filename]:
                if old_results[filename][f][m] == -1:
                  cols.append('*')
                else:
                  if round(old_results[filename][f][m], 2) == round(max_col_vals[filename], 2):
                    cols.append('\\textbf{%s}' % "{:,}".format(old_results[filename][f][m]))
                  else:
                    cols.append("{:,}".format(old_results[filename][f][m]))
              else:
                cols.append('-')

          rows.append(' & '.join(cols) + ' \\\\')
      
        rows = '\n'.join(rows)

        caption = '%s Results' % str(f).capitalize()
        print(table.substitute(caption=caption, alignments=alignments, columns=columns, rows=rows))
    

  if args.plot:
    print('========= Plot =========')

    if not old_data['results']:
      print('ERRORS: No results to use')
      exit(2)
    
    old_results = old_data['results']

    colors = [
      'tab:blue', 
      'tab:orange', 
      'tab:green', 
      'tab:red', 
      'tab:purple', 
      'tab:brown', 
      'tab:pink', 
      'tab:gray', 
      'tab:olive'
    ]

    modes = args.columns or Modes

    for m, color in zip(modes, colors):
      y_data = []
      y_timeouts = []
      for filename in old_results.keys():
        if m in old_results[filename][Fields.TIME] and old_results[filename][Fields.TIME][m]:
          y_data.append(old_results[filename][Fields.TIME][m])
        else:
          y_timeouts.append(old_data['timeouts'][m])

      y_data.sort()

      y_timeouts = y_data[-1:] + y_timeouts

      x_data = [x for x in range(len(y_data))]
      x_timeouts = [x + len(x_data) - 1 for x in range(len(y_timeouts))]

      plt.plot(x_data, y_data, 'o-', color=color, label=m)
      plt.plot(x_timeouts, y_timeouts, 'x-', color=color)

    plt.xlabel('Benchmarks')
    plt.ylabel('Time (s)')
    plt.legend()

    plt.grid(True, ls=':')

    filename = args.plot

    plt.savefig(filename, bbox_inches='tight')
    print('Saved to %s' % filename)

if __name__ == '__main__':
  main()
