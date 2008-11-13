# Copyright (c) 2006-2008 The Chromium Authors. All rights reserved.
# Use of this source code is governed by a BSD-style license that can be
# found in the LICENSE file.

"""Defines the interface TestTypeBase which other test types inherit from.

Also defines the TestArguments "struct" to pass them additional arguments.
"""

import cgi
import difflib
import os.path
import subprocess


import google.path_utils

from layout_package import path_utils
from layout_package import platform_utils

class TestArguments(object):
  """Struct-like wrapper for additional arguments needed by specific tests."""
  # Outer directory in which to place new baseline results.
  new_baseline = None

  # Whether to save new text baseline files (otherwise only save image
  # results as a new baseline).
  text_baseline = False

  # Path to the actual PNG file generated by pixel tests
  png_path = None

  # Value of checksum generated by pixel tests.
  hash = None

  # Whether to use wdiff to generate by-word diffs.
  wdiff = False

  # Whether to report the locations of the expected result files used.
  show_sources = False

class TestTypeBase(object):
  # Filename pieces when writing failures to the test results directory.
  FILENAME_SUFFIX_ACTUAL = "-actual-win"
  FILENAME_SUFFIX_EXPECTED = "-expected"
  FILENAME_SUFFIX_DIFF = "-diff-win"
  FILENAME_SUFFIX_WDIFF = "-wdiff-win.html"

  def __init__(self, platform, root_output_dir):
    """Initialize a TestTypeBase object.

    Args:
      platform: the platform (e.g., 'chromium-mac-leopard') identifying the
        platform-specific results to be used
      root_output_dir: The unix style path to the output dir.
    """
    self._root_output_dir = root_output_dir
    self._platform = platform
  
  def _MakeOutputDirectory(self, filename):
    """Creates the output directory (if needed) for a given test filename."""
    output_filename = os.path.join(self._root_output_dir,
                                   path_utils.RelativeTestFilename(filename))
    google.path_utils.MaybeMakeDirectory(os.path.split(output_filename)[0])

  def _SaveBaselineData(self, filename, dest_dir, data, modifier):
    """Saves a new baseline file.

    The file will be named simply "<test>-expected<modifier>", suitable for
    use as the expected results in a later run.

    Args:
      filename: the test filename
      dest_dir: the outer directory into which the results should be saved.
          The subdirectory corresponding to this test will be created if
          necessary.
      data: result to be saved as the new baseline
      modifier: type of the result file, e.g. ".txt" or ".png"
    """
    output_filename = os.path.join(dest_dir,
                                   path_utils.RelativeTestFilename(filename))
    output_filename = (os.path.splitext(output_filename)[0] +
                       self.FILENAME_SUFFIX_EXPECTED + modifier)
    google.path_utils.MaybeMakeDirectory(os.path.split(output_filename)[0])
    open(output_filename, "wb").write(data)

  def OutputFilename(self, filename, modifier):
    """Returns a filename inside the output dir that contains modifier.
    
    For example, if filename is c:/.../fast/dom/foo.html and modifier is
    "-expected.txt", the return value is
    c:/cygwin/tmp/layout-test-results/fast/dom/foo-expected.txt
    
    Args:
      filename: absolute filename to test file
      modifier: a string to replace the extension of filename with

    Return:
      The absolute windows path to the output filename
    """
    output_filename = os.path.join(self._root_output_dir,
                                   path_utils.RelativeTestFilename(filename))
    return os.path.splitext(output_filename)[0] + modifier

  def RelativeOutputFilename(self, filename, modifier):
    """Returns a relative filename inside the output dir that contains 
    modifier.
    
    For example, if filename is fast\dom\foo.html and modifier is
    "-expected.txt", the return value is fast\dom\foo-expected.txt
    
    Args:
      filename: relative filename to test file
      modifier: a string to replace the extension of filename with

    Return:
      The relative windows path to the output filename
    """
    return os.path.splitext(filename)[0] + modifier

  def CompareOutput(self, filename, proc, output, test_args):
    """Method that compares the output from the test with the expected value.
    
    This is an abstract method to be implemented by all sub classes.
    
    Args:
      filename: absolute filename to test file
      proc: a reference to the test_shell process
      output: a string containing the output of the test
      test_args: a TestArguments object holding optional additional arguments
    
    Return:
      a list of TestFailure objects, empty if the test passes
    """
    raise NotImplemented

  def WriteOutputFiles(self, filename, test_type, file_type, output, expected,
                       diff=True, wdiff=False):
    """Writes the test output, the expected output and optionally the diff
    between the two to files in the results directory.

    The full output filename of the actual, for example, will be
      <filename><test_type>-actual-win<file_type>
    For instance,
      my_test-simp-actual-win.txt

    Args:
      filename: The test filename
      test_type: A string describing the test type, e.g. "simp"
      file_type: A string describing the test output file type, e.g. ".txt"
      output: A string containing the test output
      expected: A string containing the expected test output
      diff: if True, write a file containing the diffs too. This should be
          False for results that are not text
      wdiff: if True, write an HTML file containing word-by-word diffs
    """
    self._MakeOutputDirectory(filename)
    actual_filename = self.OutputFilename(filename,
                      test_type + self.FILENAME_SUFFIX_ACTUAL + file_type)
    expected_win_filename = self.OutputFilename(filename,
                      test_type + self.FILENAME_SUFFIX_EXPECTED + file_type)
    open(actual_filename, "wb").write(output)
    open(expected_win_filename, "wb").write(expected)

    if diff:
      diff = difflib.unified_diff(expected.splitlines(True),
                                  output.splitlines(True),
                                  expected_win_filename,
                                  actual_filename)

      diff_filename = self.OutputFilename(filename,
                           test_type + self.FILENAME_SUFFIX_DIFF + file_type)
      open(diff_filename, "wb").write(''.join(diff))

    if wdiff:
      # Shell out to wdiff to get colored inline diffs.
      platform_util = platform_utils.PlatformUtility('')
      executable = platform_util.WDiffExecutablePath()
      cmd = [executable,
             '--start-delete=##WDIFF_DEL##', '--end-delete=##WDIFF_END##',
             '--start-insert=##WDIFF_ADD##', '--end-insert=##WDIFF_END##',
             actual_filename, expected_win_filename]
      filename = self.OutputFilename(filename,
                      test_type + self.FILENAME_SUFFIX_WDIFF)
      wdiff = subprocess.Popen(cmd, stdout=subprocess.PIPE).communicate()[0]
      wdiff = cgi.escape(wdiff)
      wdiff = wdiff.replace('##WDIFF_DEL##', '<span class=del>')
      wdiff = wdiff.replace('##WDIFF_ADD##', '<span class=add>')
      wdiff = wdiff.replace('##WDIFF_END##', '</span>')
      out = open(filename, 'wb')
      out.write('<head><style>.del { background: #faa; } ')
      out.write('.add { background: #afa; }</style></head>')
      out.write('<pre>' + wdiff + '</pre>')
      out.close()
