# import matplotlib.pyplot as plt
import os 
import argparse
import subprocess
import json
import re
import matplotlib.pyplot as plt
from string import Template
from enum import Enum

class Fields(str, Enum):
  TIME = 'time'
  SIZE = 'size'
  CALLS = 'calls'

class Modes(str, Enum):
  NOOPT = 'no opts'
  DET = 'det'
  FH = 'fh + det + be'
  SBK = 'sbk + det + be'
  SBKFH = 'sbk + fh + det + be'
  EA = 'ea + det + be'
  EAFH = 'ea + fh + det + be'
  EASBK = 'ea + sbk + det + be'
  EASBKFH = 'eg + sbk + fh + det + be'

  def __str__(self):
    return self.name

  @staticmethod
  def from_string(s):
    try:
      return Modes[s]
    except KeyError:
      raise ValueError()

def get_mode_cmd(mode):
  if mode == Modes.NOOPT:
    return []
  if mode == Modes.DET:
    return ['-determinism']
  if mode == Modes.FH:
    return ['-determinism', '-flip-lifting', '-branch-elimination']
  if mode == Modes.SBK:
    return ['-determinism', '-sbk-encoding', '-branch-elimination']
  if mode == Modes.SBKFH:
    return ['-determinism', '-flip-lifting', '-sbk-encoding', '-branch-elimination']
  if mode == Modes.EA:
    return ['-eager-eval', '-determinism', '-branch-elimination']
  if mode == Modes.EAFH:
    return ['-eager-eval', '-flip-lifting', '-determinism', '-branch-elimination']
  if mode == Modes.EASBK:
    return ['-eager-eval', '-sbk-encoding', '-determinism', '-branch-elimination']
  if mode == Modes.EASBKFH:
    return ['-eager-eval', '-sbk-encoding', '-flip-lifting', '-determinism', '-branch-elimination']
  
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
        p = subprocess.run(['/usr/bin/time', '-f', "%e", dice_path, file, '-skip-table'] + cmd, 
          capture_output=True, timeout=timeout)

        pattern = re.compile('^(\d+.?\d*)$')
        matches = pattern.match(p.stderr.decode('utf-8'))
        if matches:
          results[Fields.TIME][mode] = float(matches.group(1))
        else:
          results[Fields.TIME][mode] = -1
          print('ERROR:')
          print(p.stderr.decode('utf-8'))

      except subprocess.TimeoutExpired:
        print('TIMEOUT')

    print()
  
  if Fields.SIZE in fields or Fields.CALLS in fields:
    print('Measuring BDD size and/or number of recursive calls...')
    cmd = [dice_path, file, '-skip-table']
    if Fields.SIZE in fields:
      cmd.append('-show-size')
    if Fields.CALLS in fields:
      cmd.append('-num-recursive-calls')

    for mode in modes:
      mode_cmd = get_mode_cmd(mode)
      if mode_cmd is None:
        print('UNKNOWN MODE')
        continue

      print('Mode:', mode)

      try:
        p = subprocess.run(cmd + mode_cmd, capture_output=True, timeout=timeout)
        output = p.stdout.decode('utf-8')
        call_pattern = re.compile('================\[ Number of recursive calls \]================\s(\d+.?\d*)')
        size_pattern = re.compile('================\[ Final compiled BDD size \]================\s(\d+.?\d*)')
        
        call_matches = call_pattern.search(output)
        size_matches = size_pattern.search(output)

        if call_matches:
          results[Fields.CALLS][mode] = int(float(call_matches.group(1)))
        
        if size_matches:
          results[Fields.SIZE][mode] = int(float(size_matches.group(1)))

        if not call_matches and not size_matches:
          results[Fields.SIZE][mode] = -1
          results[Fields.CALLS][mode] = -1
          print('ERROR:')
          print(p.stdout.decode('utf-8'))

      except subprocess.TimeoutExpired:
        print('TIMEOUT')

    print()

  return results


def main():
  parser = argparse.ArgumentParser(description="Test harness for Dice experiments.")
  parser.add_argument('-i', '--dir', type=str, nargs=1, help='directory of experiment Dice files')
  parser.add_argument('-d', '--dice', type=str, nargs=1, help='path to Dice')
  parser.add_argument('-o', '--out', type=str, nargs=1, help='path to output file. Defaults to results.json')
  parser.add_argument('--table', action='store_true', help='prints data from output file as Latex table')
  parser.add_argument('--plot', action='store_true', help='generate cactus plot')

  parser.add_argument('--timeout', type=int, nargs=1, help='sets timeout in seconds')
  parser.add_argument('-t', '--time', dest='fields', action='append_const', const=Fields.TIME, help='record time elapsed')
  parser.add_argument('-s', '--size', dest='fields', action='append_const', const=Fields.SIZE, help='record BDD size')
  parser.add_argument('-c', '--calls', dest='fields', action='append_const', const=Fields.CALLS, help='record number of recursive calls')

  parser.add_argument('--modes', nargs='*', type=Modes.from_string, choices=list(Modes), help='select modes to run over')

  args = parser.parse_args()
  
  if args.out:
    out = args.out[0]
  else:
    out = 'results.json'

  old_data = {
    'timeouts': {m:None for m in Modes},
    'results': {}
  }

  if os.path.exists(out):
    with open(out, 'r') as f:
      old_data = json.load(f)

  if args.dir:
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

    table = Template("""\\begin{table}[H]
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
      modes = [m for m in Modes]
      columns = " & ".join(modes)
      alignments = 'l' + 'r' * len(modes)
      rows = []

      for filename in old_results.keys():
        cols = ['\\textsc{' + filename.split('.')[0].replace('_', '\_') + '}']
      
        for m in modes:
          cols.append('%.2f' % old_results[filename][f][m] if m in old_results[filename][f] and old_results[filename][f][m] else 'N/A')

        rows.append(' & '.join(cols) + ' \\\\')
    
      rows = '\n'.join(rows)

      caption = '%s results' % f
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

    for m, color in zip(Modes, colors):
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

    plt.savefig('cactus_plot.png', bbox_inches='tight')
    print('Saved to %s' % 'cactus_plot.png')

if __name__ == '__main__':
  main()
