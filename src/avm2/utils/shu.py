#!/usr/bin/env python
import sys,os.path,os,getopt,time,subprocess,re,argparse,threading
from pprint import pprint

from subprocess import Popen, PIPE, STDOUT
import datetime, time, signal
import pickle
import Queue
import multiprocessing
import tempfile

from dis import disassemble

def execute (command, timeout = -1):
  start_time = time.time()
  # print "run: ", command
  processPid = [None]
  stdoutOutput = [None]
  stderrOutput = [None]
  def target():
    process = Popen(command, stdout=PIPE, stderr=STDOUT, close_fds=True)
    processPid[0] = process.pid;
    (stdoutOutput[0], stderrOutput[0]) = process.communicate();

  thread = threading.Thread(target=target)
  thread.start()
  # print "Timeout", timeout
  thread.join(timeout)
  if thread.is_alive():
    # Kill Process
    os.kill(processPid[0], signal.SIGKILL)
    os.waitpid(-1, os.WNOHANG)
    thread.join()

  elapsed_time = time.time() - start_time
  output = stdoutOutput[0]
  return (output.strip(), elapsed_time);

class Base:
  asc = None
  avm = None
  builtin_abc = None

  def __init__(self):
    self.setEnvironmentVariables();
    pass

  def setEnvironmentVariables(self):
    if 'ASC' in os.environ:
      self.asc = os.environ['ASC'].strip();
    else:
      print "Environment variable ASC is not defined, set it to asc.jar"

    if 'BUILTINABC' in os.environ:
      self.builtin_abc = os.environ['BUILTINABC'].strip();
    else:
      print "Environment variable BUILTINABC is not defined, set it to builtin.abc"

    # The builtin.abc cannot be combined with the playerglobal.abc file that comes with Alchemy, thus we need
    # this other global.abc library.

    if 'GLOBALABC' in os.environ:
      self.global_abc = os.environ['GLOBALABC'].strip();

    if 'PLAYERGLOBALABC' in os.environ:
      self.player_global_abc = os.environ['PLAYERGLOBALABC'].strip();

    if 'AVM' in os.environ:
      self.avm = os.environ['AVM']
    else:
      print "Environment variable AVM is not defined, set it to avmshell"


    if not self.asc:
      sys.exit();

  def runAsc(self, files, createSwf = False, builtin = False, _global = False, playerGlobal = False, sc = False):
    if sc:
      outf = os.path.splitext(files[-1])[0]
      args = ["java", "-ea", "-DAS3", "-DAVMPLUS", "-classpath", self.asc,
              "macromedia.asc.embedding.ScriptCompiler", "-d", "-out", outf]
    else:
      args = ["java", "-ea", "-DAS3", "-DAVMPLUS", "-jar", self.asc, "-d"]

    if builtin:
      args.extend(["-import", self.builtin_abc])

    if _global:
      args.extend(["-import", self.global_abc])

    if playerGlobal:
      args.extend(["-import", self.player_global_abc])

    args.extend(files);
    print(args)
    subprocess.call(args)
    if createSwf:
      args = ["java", "-jar", self.asc, "-swf", "cls,1,1", "-d"]
      args.extend(files)
      subprocess.call(args)

    if sc:
      os.remove(outf + ".cpp")
      os.remove(outf + ".h")

  def runAvm(self, file, execute = True, trace = False, disassemble = False):
    args = ["js", "-m", "-n", "avm.js"];
    if disassemble:
      args.append("-d")
    if not trace:
      args.append("-q")
    if execute:
      args.append("-x")
    args.append(file)
    subprocess.call(args)

class Command(Base):
  name = ""

  def __init__(self, name):
    Base.__init__(self)
    self.name = name


class Asc(Command):
  def __init__(self):
    Command.__init__(self, "asc")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Compiles an ActionScript source file to .abc or .swf using the asc.jar compiler.')
    parser.add_argument('src', nargs='+', help="source .as file")
    parser.add_argument('-builtin', action='store_true', help='import builtin.abc')
    parser.add_argument('-globals', action='store_true', help='import global.abc')
    parser.add_argument('-playerGlobal', action='store_true', help='import playerGlobal.abc')
    parser.add_argument('-sc', action='store_true', help='use embedding.ScriptCompiler (needed to compile multiple scripts into one .abc file)')
    parser.add_argument('-swf', action='store_true', help='optionally package compiled file in a .swf file')
    args = parser.parse_args(args)
    print "Compiling %s" % args.src
    self.runAsc(args.src, args.swf, builtin = args.builtin, _global = args.globals, playerGlobal = args.playerGlobal,  sc = args.sc)

class Ascreg(Command):
  def __init__(self):
    Command.__init__(self, "ascreg")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Compiles all the source files in the test/regress directory using the asc.jar compiler.')
    parser.add_argument('src', default="../tests/regress", help="source .as file")
    args = parser.parse_args(args)
    print "Compiling Tests"

    tests = [];
    if os.path.isdir(args.src):
      for root, subFolders, files in os.walk("../tests/regress"):
        for file in files:
          if file.endswith(".as") and file != "harness.as":
            tests.append(os.path.join(root, file))
    else:
      tests.append(os.path.abspath(args.src))

    for test in tests:
      args = ["java", "-jar", self.asc, "-d", "-import", self.builtin_abc, "-in", "../tests/regress/harness.as", test]
      subprocess.call(args)

class Avm(Command):
  def __init__(self):
    Command.__init__(self, "avm")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Runs an .abc file using Shumway AVM')
    parser.add_argument('src', help="source .abc file")
    parser.add_argument('-trace', action='store_true', help="trace bytecode execution")
    args = parser.parse_args(args)
    print "Running %s" % args.src
    self.runAvm(args.src, trace = args.trace)

class Dis(Command):
  def __init__(self):
    Command.__init__(self, "dis")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Disassembles an .abc file ')
    parser.add_argument('src', help="source .abc file")
    args = parser.parse_args(args)
    print "Disassembling %s" % args.src
    self.runAvm(args.src, execute = False, disassemble = True)

class Compile(Command):
  def __init__(self):
    Command.__init__(self, "compile")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Compiles an .abc file to .js ')
    parser.add_argument('src', help="source .abc file")
    parser.add_argument('-trace', action='store_true', help="trace bytecode execution")
    args = parser.parse_args(args)
    print "Compiling %s" % args.src
    self.runAvm(args.src, trace = args.trace, execute = True)

class Test(Command):
  def __init__(self):
    Command.__init__(self, "test")

  def __repr__(self):
    return self.name

  def execute(self, args):
    parser = argparse.ArgumentParser(description='Runs all tests.')
    parser.add_argument('src', help=".abc search path")
    parser.add_argument('-j', '--jobs', type=int, default=multiprocessing.cpu_count(), help="number of jobs to run in parallel")
    parser.add_argument('-t', '--timeout', type=int, default=20, help="timeout (s)")
    parser.add_argument('-i', '--interpret', action='store_true', default=True, help="always interpret")
    parser.add_argument('-c', '--compile', action='store_true', default=False, help="always compile")
    parser.add_argument('-n', '--noColors', action='store_true', help="disable colors")

    args = parser.parse_args(args)
    print "Testing %s" % (args.src)

    print "---------------------------------------------------------------------------------------------------------"
    print "Each Tamarin acceptance test case includes a bunch of smaller tests, each of which print out PASSED or"
    print "FAILED. We compare the output under several configurations and print the results as follows:"
    print "PASSED - output matches AVM Shell"
    print "ALMOST - the \"PASSED\" string appears in the output but the \"FAILED\" string does not."
    print "KINDOF - the \"PASSED\" and \"FAILED\" string appear in the output."
    print "FAILED - the \"PASSED\" string doesn't appear anywhere."
    print "---------------------------------------------------------------------------------------------------------"
    print "Interpreter Time, Time Ratio, Compiler, Time, Time Ratio, Interpreter/Compiler, Time Ratio, Number, File"
    print "---------------------------------------------------------------------------------------------------------"

    tests = Queue.Queue();

    if os.path.isdir(args.src):
      for root, subFolders, files in os.walk(args.src):
        for file in files:
          if file.endswith(".abc"):
            tests.put(os.path.join(root, file))
    elif args.src.endswith(".abc"):
      tests.put(os.path.abspath(args.src))

    INFO = '\033[94m'
    WARN = '\033[93m'
    PASS = '\033[92m'
    FAIL = '\033[91m'
    ENDC = '\033[0m'

    if args.noColors:
      INFO = WARN = PASS = FAIL = ENDC = "";

    total = tests.qsize()
    counts = {
      'passed-i': 0,
      'almost-i': 0,
      'kindof-i': 0,
      'failed-i': 0,
      'passed-c': 0,
      'almost-c': 0,
      'kindof-c': 0,
      'failed-c': 0,
      'count': 0,
    }

    def runTest(tests, counts):
      while tests.qsize() > 0:
        test = tests.get()
        out = []
        counts['count'] += 1

        results = []
        results.append(execute([self.avm, test], int(args.timeout)))
        if args.compile:
          results.append(execute(["js", "-m", "-n", "avm.js", "-x", "-i", test], int(args.timeout)))
        if args.interpret:
          results.append(execute(["js", "-m", "-n", "avm.js", "-x", test], int(args.timeout)))

        for i in range (1, len(results)):
          base = results[0]
          result = results[i]
          suffix = "c" if i == 2 else "i"
          if base[0] == result[0]:
            out.append(PASS + "PASSED" + ENDC)
            counts["passed-" + suffix] += 1;
          else:
            if "PASSED" in result[0] and not "FAILED" in result[0]:
              out.append(INFO + "ALMOST"  + ENDC)
              counts["almost-" + suffix] += 1;
            elif "PASSED" in result[0] and "FAILED" in result[0]:
              out.append(WARN + "KINDOF"  + ENDC)
              counts["kindof-" + suffix] += 1;
            else:
              out.append(FAIL + "FAILED"  + ENDC)
              counts["failed-" + suffix] += 1;

          out.append(str(round(result[1], 2)))
          ratio = round(base[1] / result[1], 2)
          out.append((WARN if ratio < 1 else INFO) + str(ratio) + ENDC)

        if args.compile:
          if results[1][0] == results[2][0]:
            out.append(PASS + "MATCH"  + ENDC)
          else:
            out.append(FAIL + "DIFFER"  + ENDC)
          ratio = round(results[1][1] / results[2][1], 2)
          out.append((WARN if ratio < 1 else INFO) + str(ratio) + ENDC)

        out.append(str(round(result[1], 2)))
        out.append(str(total - tests.qsize()))
        out.append(test);
        sys.stdout.write("\t".join(out) + "\n")
        sys.stdout.flush()

        tests.task_done()

    jobs = []
    for i in range(int(args.jobs)):
      job = threading.Thread(target=runTest, args=(tests, counts))
      job.start()
      jobs.append(job)

    tests.join()

    for job in jobs:
      job.join()

    pprint (counts)

#    print "Results: failed: " + FAIL + str(counts['failed']) + ENDC + ", passed: " + PASS + str(counts['passed']) + ENDC + " of " + str(total),
#    print "shuElapsed: " + str(round(counts['shuElapsed'] * 1000, 2)) + " ms",
#    print "avmElapsed: " + str(round(counts['avmElapsed'] * 1000, 2)) + " ms",
#    if counts['shuElapsed'] > 0:
#      print str(round(counts['avmElapsed'] / counts['shuElapsed'], 2)) + "x faster" + ENDC

commands = {}
for command in [Asc(), Avm(), Dis(), Compile(), Test(), Ascreg()]:
  commands[str(command)] = command;

parser = argparse.ArgumentParser()
parser.add_argument('command', help=",".join(commands.keys()))
args = parser.parse_args(sys.argv[1:2])

if (not args.command in commands):
  print "Invalid command: %s" % args.command
  parser.print_help()

command = commands[args.command];
command.execute(sys.argv[2:])
