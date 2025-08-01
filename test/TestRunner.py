"""
https://gist.github.com/viniciusd/73e6eccd39dea5e714b1464e3c47e067
A TestRunner for use with the Python unit testing framework. It
generates a tabular report to show the result at a glance.

The simplest way to use this is to invoke its main method. E.g.

    import unittest
    import TestRunner

    ... define your tests ...

    if __name__ == '__main__':
        TestRunner.main()

    # run the test
    runner.run(my_test_suite)


This TestRunner is based on HTMLTestRunner <http://tungwaiyip.info/software/HTMLTestRunner.html>
It is likely that I will rewrite this module form scracth soon.
By the way, HTMLTestRunner's license does not cover forking, given that I removed HTMLTestRunner's main characteristic(the HTML), I decided also removing the license. If I did not interpret the license properly, please, let me know.
HTMLTestRunner's author is Wai Yip Tung and I am grateful for his contribution.
"""

import datetime

try:
    from StringIO import StringIO
except ImportError:
    from io import StringIO
import sys
import re
import humanize
import unittest


class Config:
    PRINT_LIVE = True
    SINGLE_LINE_STACK = True


# ------------------------------------------------------------------------
# The redirectors below are used to capture output during testing. Output
# sent to sys.stdout and sys.stderr are automatically captured. However
# in some cases sys.stdout is already cached before HTMLTestRunner is
# invoked (e.g. calling logging.basicConfig). In order to capture those
# output, use the redirectors for the cached stream.
#
# e.g.
#   >>> logging.basicConfig(stream=HTMLTestRunner.stdout_redirector)
#   >>>

class OutputRedirector(object):
    """ Wrapper to redirect stdout or stderr """

    def __init__(self, fp):
        self.fp = fp

    def write(self, s):
        self.fp.write(s)

    def writelines(self, lines):
        self.fp.writelines(lines)

    def flush(self):
        self.fp.flush()


stdout_redirector = OutputRedirector(sys.stdout)
stderr_redirector = OutputRedirector(sys.stderr)


class Table(object):

    def __init__(self, padding='', allow_newlines=False):
        self.__columnSize__ = []
        self.__rows__ = []
        self.__titles__ = None
        self.padding = padding
        self.allow_newlines = allow_newlines

    def __len__(self, x):
        return len(re.sub(r"\033\[[0-9];[0-9];[0-9]{1,2}m", "", x))

    def addRow(self, row):
        rows = [[''] for l in range(len(row))]
        maxrows = 1
        for i, x in enumerate(row):
            for j, y in enumerate(x.split("\n")):
                if len(y) == 0 and self.allow_newlines == False:
                    continue
                try:
                    self.__columnSize__[i] = max(self.__columnSize__[i], self.__len__(y))
                except IndexError:
                    self.__columnSize__.append(self.__len__(y))
                rows[i].append(y)
                maxrows = max(j, maxrows)
        for i in range(len(rows)):
            rows[i] += (maxrows - (len(rows[i]) - 1)) * ['']
        for i in range(maxrows):
            self.__rows__.append([rows[j][i + 1] for j in range(len(row))])

    def addTitles(self, titles):
        for i, x in enumerate(titles):
            try:
                self.__columnSize__[i] = max(self.__columnSize__[i], self.__len__(x))
            except IndexError:
                self.__columnSize__.append(self.__len__(x))
        self.__titles__ = titles

    def __repr__(self):
        hline = self.padding + "+"
        for x in self.__columnSize__:
            hline += (x + 2) * '-' + '+'
        rows = []
        if self.__titles__ is None:
            title = ""
        else:
            if len(self.__titles__) < len(self.__columnSize__):
                self.__titles__ += ((len(self.__columnSize__) - len(self.__titles__)) * [''])
            for i, x in enumerate(self.__titles__):
                self.__titles__[i] = x.center(self.__columnSize__[i])
            title = self.padding + "| " + " | ".join(self.__titles__) + " |\n" + hline + "\n"
        for x in self.__rows__:
            if len(x) < len(self.__columnSize__):
                x += ((len(self.__columnSize__) - len(x)) * [''])
            for i, c in enumerate(x):
                x[i] = c.ljust(self.__columnSize__[i]) + (len(c) - self.__len__(c) - 3) * ' '
            rows.append(self.padding + "| " + " | ".join(x) + " |")
        return hline + "\n" + title + "\n".join(rows) + "\n" + hline + "\n"


class bcolors(object):
    FORMAT = {
        'Regular': '0',
        'Bold': '1',
        'Underline': '4',
        'High Intensity': '0',  # +60 on color
        'BoldHighIntensity': '1',  # +60 on color
    }
    START = "\033["
    COLOR = {
        'black': "0;30m",
        'red': "0;31m",
        'green': "0;32m",
        'yellow': "0;33m",
        'blue': "0;34m",
        'purple': "0;35m",
        'cyan': "0;36m",
        'white': "0;37m",
        'end': "0m",
    }

    def __getattr__(self, name):
        def handlerFunction(*args, **kwargs):
            return self.START + self.FORMAT['Regular'] + ";" + self.COLOR[name.lower()]

        return handlerFunction(name=name)
    # ----------------------------------------------------------------------


# Template

class Template_mixin(object):
    bc = bcolors()

    STATUS = {
        0: bc.GREEN + 'pass' + bc.END,
        1: bc.PURPLE + 'fail' + bc.END,
        2: bc.RED + 'error' + bc.END,
    }

    # ------------------------------------------------------------------------
    # Report
    #

    REPORT_TEST_WITH_OUTPUT_TMPL = r"""
   %(desc)s

        %(status)s

        %(script)s

"""  # variables: (tid, Class, style, desc, status)

    REPORT_TEST_NO_OUTPUT_TMPL = r"""
    %(desc)s
    %(status)s
"""  # variables: (tid, Class, style, desc, status)

    REPORT_TEST_OUTPUT_TMPL = r"""
%(output)s
"""  # variables: (id, output)


# -------------------- The end of the Template class -------------------


TestResult = unittest.TestResult


class _TestResult(TestResult):
    # note: _TestResult is a pure representation of results.
    # It lacks the output and reporting ability compares to unittest._TextTestResult.

    def __init__(self, verbosity=1):
        TestResult.__init__(self)
        self.stdout0 = None
        self.stderr0 = None
        self.success_count = 0
        self.failure_count = 0
        self.error_count = 0
        self.verbosity = verbosity

        # result is a list of result in 4 tuple
        # (
        #   result code (0: success; 1: fail; 2: error),
        #   TestCase object,
        #   Test output (byte string),
        #   stack trace,
        # )
        self.result = []
        #
        self.outputBuffer = StringIO()

    def startTest(self, test):
        TestResult.startTest(self, test)
        # just one buffer for both stdout and stderr
        self.outputBuffer = StringIO()
        stdout_redirector.fp = self.outputBuffer
        stderr_redirector.fp = self.outputBuffer
        self.stdout0 = sys.stdout
        self.stderr0 = sys.stderr
        sys.stdout = stdout_redirector
        sys.stderr = stderr_redirector

    def complete_output(self):
        """
        Disconnect output redirection and return buffer.
        Safe to call multiple times.
        """
        if self.stdout0:
            sys.stdout = self.stdout0
            sys.stderr = self.stderr0
            self.stdout0 = None
            self.stderr0 = None
        return self.outputBuffer.getvalue()

    def stopTest(self, test):
        # Usually one of addSuccess, addError or addFailure would have been called.
        # But there are some path in unittest that would bypass this.
        # We must disconnect stdout in stopTest(), which is guaranteed to be called.
        self.complete_output()

    def addSuccess(self, test):
        self.success_count += 1
        TestResult.addSuccess(self, test)
        output = self.complete_output()
        self.result.append((0, test, output, ''))
        if self.verbosity > 1:
            sys.stderr.write('ok ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            if Config.PRINT_LIVE:
                sys.stderr.write('.')

    def addError(self, test, err):
        self.error_count += 1

        # Remove the traceback object to have single line error
        if Config.SINGLE_LINE_STACK:
            err = (err[0], err[1], None)

        TestResult.addError(self, test, err)
        _, _exc_str = self.errors[-1]
        output = self.complete_output()
        self.result.append((2, test, output, _exc_str))
        if self.verbosity > 1:
            sys.stderr.write('E  ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            if Config.PRINT_LIVE:
                sys.stderr.write('E')

    def addFailure(self, test, err):
        self.failure_count += 1

        # Remove traceback to have single line failure
        if Config.SINGLE_LINE_STACK:
            # Replaces old exception with new instance with updated error message that is a single line
            new_err = err[1].__class__(str(err[1]).replace("\n", "")[0])
            err = (err[0], new_err, None)

        TestResult.addFailure(self, test, err)
        _, _exc_str = self.failures[-1]
        output = self.complete_output()
        self.result.append((1, test, output, _exc_str))
        if self.verbosity > 1:
            sys.stderr.write('F  ')
            sys.stderr.write(str(test))
            sys.stderr.write('\n')
        else:
            if Config.PRINT_LIVE:
                sys.stderr.write('F')


class TestRunner(Template_mixin):
    """
    """

    def __init__(self, stream=sys.stdout, verbosity=1, title=None, description=None):
        self.stream = stream
        self.verbosity = verbosity
        if title is None:
            self.title = 'Unit Test Report'
        else:
            self.title = title
        if description is None:
            self.description = ''
        else:
            self.description = description

        self.startTime = datetime.datetime.now()
        self.bc = bcolors()

    def run(self, test):
        "Run the given test case or test suite."
        result = _TestResult(self.verbosity)
        test(result)
        self.stopTime = datetime.datetime.now()
        self.generateReport(test, result)
        return result

    def sortResult(self, result_list):
        # unittest does not seems to run in any particular order.
        # Here at least we want to group them together by class.
        rmap = {}
        classes = []
        for n, test, output, error in result_list:
            testClass = test.__class__
            if testClass not in rmap:
                rmap[testClass] = []
                classes.append(testClass)
            rmap[testClass].append((n, test, output, error))
        r = [(testClass, rmap[testClass]) for testClass in classes]
        return r

    def getReportAttributes(self, result):
        """
        Return report attributes as a list of (name, value).
        Override this to add custom attributes.
        """
        startTime = str(self.startTime)[:19]
        duration = str(self.stopTime - self.startTime)
        status = []
        padding = 4 * ' '
        status.append(padding + self.bc.GREEN + 'Pass   ' + self.bc.END + ' : %s\n' % result.success_count)
        status.append(padding + self.bc.PURPLE + 'Failure' + self.bc.END + ' : %s\n' % result.failure_count)
        status.append(padding + self.bc.RED + 'Error  ' + self.bc.END + ' : %s\n' % result.error_count)

        if status:
            status = '\n' + ''.join(status)
        else:
            status = 'none'
        return [
            ('Start Time', startTime),
            ('Duration', duration),
            ('Status', status),
        ]

    def generateReport(self, test, result):
        report_attrs = self.getReportAttributes(result)
        heading = self._generate_heading(report_attrs)
        report = self._generate_report(result)
        output = "\n" + self.title + "\n" + \
                 heading + \
                 report
        try:
            time_elapsed = (self.stopTime - self.startTime)
            sys.stderr.write('\nTests took %s - (%s)\n' % (humanize.naturaldelta(time_elapsed), time_elapsed))
            self.stream.write(output.encode('utf8'))
        except TypeError:
            self.stream.write(output)

    def _generate_heading(self, report_attrs):
        a_lines = []
        for name, value in report_attrs:
            line = self.bc.CYAN + name + ": " + self.bc.END + value + "\n"
        a_lines.append(line)
        heading = ''.join(a_lines) + \
                  self.bc.CYAN + "Description:" + self.bc.END + self.description + "\n"
        return heading

    def _generate_report(self, result):
        rows = []
        sortedResult = self.sortResult(result.result)
        padding = 4 * ' '
        table = Table(padding=padding)
        table.addTitles(["Test group/Test case", "Count", "Pass ", "Fail ", "Error"])
        tests = ''
        for cid, (testClass, classResults) in enumerate(sortedResult):  # Iterate over the test cases
            classTable = Table(padding=2 * padding)
            classTable.addTitles(["Test Name", "Stack", "Status"])
            # subtotal for a class
            np = nf = ne = 0
            for n, t, o, e in classResults:
                if n == 0:
                    np += 1
                elif n == 1:
                    nf += 1
                else:
                    ne += 1

            # format class description
            if testClass.__module__ == "__main__":
                name = testClass.__name__
            else:
                name = "%s" % testClass.__name__

            # Color classname header blue
            tests += "\n" + padding + self.bc.CYAN + name + self.bc.END + "\n"
            doc = testClass.__doc__ and testClass.__doc__.split("\n")[0] or ""
            desc = doc and '%s: %s' % (name, doc) or name
            # style = ne > 0 and 'errorClass' or nf > 0 and 'failClass' or 'passClass',

            table.addRow([desc, str(np + nf + ne), str(np), str(nf), str(ne)])
            for tid, (n, test, output, error) in enumerate(classResults):  # Iterate over the unit tests
                classTable.addRow(self._generate_report_test(cid, tid, n, test, output, error))
            tests += str(classTable)
        table.addRow(
            ["Total", str(result.success_count + result.failure_count + result.error_count), str(result.success_count),
             str(result.failure_count), str(result.error_count)])
        report = self.bc.CYAN + "Summary: " + self.bc.END + "\n" + str(table) + tests
        return report

    def _generate_report_test(self, cid, tid, n, test, output, error):
        has_output = bool(output or error)
        tid = (n == 0 and 'p' or 'f') + 't%s.%s' % (cid + 1, tid + 1)
        name = test.id().split('.')[-1]
        doc = test.shortDescription() or ""
        desc = doc and ('%s: %s' % (name, doc)) or name
        tmpl = has_output and self.REPORT_TEST_WITH_OUTPUT_TMPL or self.REPORT_TEST_NO_OUTPUT_TMPL

        # o and e should be byte string because they are collected from stdout and stderr?
        if isinstance(output, str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # uo = unicode(o.encode('string_escape'))
            try:
                uo = output.decode('latin-1')
            except AttributeError:
                uo = output
        else:
            uo = output
        if isinstance(error, str):
            # TODO: some problem with 'string_escape': it escape \n and mess up formating
            # ue = unicode(e.encode('string_escape'))
            try:
                ue = error.decode('latin-1')
            except AttributeError:
                ue = error
        else:
            ue = error

        script = self.REPORT_TEST_OUTPUT_TMPL % dict(
            output=uo + ue,
        )
        row = [desc, script, self.STATUS[n]]
        # row = tmpl % dict(
        #    tid = tid,
        #    desc = desc,
        #    script = script,
        #    status = self.STATUS[n],
        # )
        return row
        # if not has_output:
        #    return


##############################################################################
# Facilities for running tests from the command line
##############################################################################

# Note: Reuse unittest.TestProgram to launch test. In the future we may
# build our own launcher to support more specific command line
# parameters like test title, CSS, etc.
class TestProgram(unittest.TestProgram):
    """
    A variation of the unittest.TestProgram. Please refer to the base
    class for command line parameters.
    """

    def runTests(self):
        # Pick TestRunner as the default test runner.
        # base class's testRunner parameter is not useful because it means
        # we have to instantiate TestRunner before we know self.verbosity.
        if self.testRunner is None:
            self.testRunner = TestRunner(verbosity=self.verbosity)
        unittest.TestProgram.runTests(self)

main = TestProgram

##############################################################################
# Executing this module from the command line
##############################################################################

# if __name__ == "__main__":
#     print("w")
#     result = main(module=None)  # This returns the TestProgram, not result
#     print("x")
#     success = result.result.wasSuccessful()
#     print(success, "AAJDJASDJASDJA")
#     sys.exit(0 if success else 1)
