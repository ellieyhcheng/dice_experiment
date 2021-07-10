# import matplotlib.pyplot as plt
import os 
import argparse
import subprocess
import json
import re
import pandas
from string import Template

def run(file, dice_path, timeout=None):
  print('File:', file)

  results = {
    'time': None
  }

  if timeout:
    print('Measuring time elapsed...')
    try:
      p = subprocess.run(['/usr/bin/time', '-f', "%e", dice_path, file, '-skip-table'], 
        capture_output=True, timeout=timeout)

      pattern = re.compile('^(\d+.?\d*)$')
      if pattern:
        results['time'] = float(pattern.match(p.stderr.decode('utf-8')).group(1))
      else:
        results['time'] = -1
        print('ERROR:')
        print(p.stderr.decode('utf-8'))

    except subprocess.TimeoutExpired:
      print('TIMEOUT')

  print()
  return results


def main():
  parser = argparse.ArgumentParser(description="Test harness for Dice experiments.")
  parser.add_argument('-i', '--dir', type=str, nargs=1, help='directory of experiment Dice files')
  parser.add_argument('-d', '--dice', type=str, nargs=1, help='path to Dice')
  parser.add_argument('-o', '--out', type=str, nargs=1, help='path to output file. Defaults to results.json')
  parser.add_argument('-t', '--time', type=int, nargs=1, help='sets timeout in seconds for time elapsed')
  parser.add_argument('-r', '--replace', action='store_true', help='overwrite existing data')
  parser.add_argument('--table', action='store_true', help='prints data from output file as Latex table')
  args = parser.parse_args()

  results = {}

  if args.out:
    out = args.out[0]
  else:
    out = 'results.json'

  if args.dir:
    files = args.dir[0]
    if not os.path.isdir(files):
      print('Invalid directory specified:', files)
      exit(2)
    else:
      print('Experiment dir:', files)
      print('Output file:', out)

      if args.time:
        print('Timeout:', args.time[0])
        timeout = args.time[0]
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
          results[filename] = run(file, dice_path, timeout)

      print()

  old_results = {}

  if os.path.exists(out):
    with open(out, 'r') as f:
      old_results = json.load(f)
    
  for filename in results.keys():
    if filename in old_results:
      for key in results[filename]:
        if args.replace or not key in old_results:
          old_results[filename][key] = results[filename][key]
    else:
      old_results[filename] = results[filename]
    
  with open(out, 'w') as f:
    json.dump(old_results, f, indent=4)
  
  if args.table:
    table = Template("""\\begin{tabular}{$alignments}
\\toprule
Benchmarks & $columns \\\\
\\midrule
$rows
\\bottomrule
\\end{tabular}""")

    fields = ['time']
    columns = " & ".join(fields)
    columns = columns.capitalize()
    alignments = 'l' + 'r' * len(fields)
    rows = []
    for filename in old_results.keys():
      cols = ['\\textsc{' + filename.split('.')[0].replace('_', '\_') + '}']
      
      for field in fields:
        cols.append('%.2f' % old_results[filename][field] if old_results[filename][field] else 'N/A')

      rows.append(' & '.join(cols) + ' \\\\')
    
    rows = '\n'.join(rows)

    print('========= Table =========')
    print(table.substitute(alignments=alignments, columns=columns, rows=rows))

if __name__ == '__main__':
  main()
