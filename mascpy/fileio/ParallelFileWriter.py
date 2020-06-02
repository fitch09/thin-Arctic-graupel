# Copyright (c) 2015-2016, Particle Flux Analytics
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
# 
# 1. Redistributions of source code must retain the above copyright notice, this
#    list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright notice,
#    this list of conditions and the following disclaimer in the documentation
#    and/or other materials provided with the distribution.
# 
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE IMPLIED
# WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE ARE
# DISCLAIMED. IN NO EVENT SHALL THE COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR
# ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR SERVICES;
# LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION) HOWEVER CAUSED AND
# ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT LIABILITY, OR TORT
# (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY OUT OF THE USE OF THIS
# SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF SUCH DAMAGE.
# 
# The views and conclusions contained in the software and documentation are those
# of the authors and should not be interpreted as representing official policies,
# either expressed or implied, of the FreeBSD Project.
# 


import multiprocessing


class ParallelFileWriter(object):
    """ File writer specialized to work with multiple threads. The key idea is to synchronize using a mutex and
        ensure the data is written in the order based on an index (lowest first, starts with 0)
    """

    def __init__(self, filename, openas = 'a', headerToWrite = ''):
        """ Initializes the writer and opens a file with a specific mode. By default opens files for appending
            but this can also be overwritten.

            :param filename: path to the file to open for writing
            :param openas: standard python file open mode (a, w)
            :param headerToWrite: header string to write (only when openas == 'w')
        """
        self._fileName = filename

        # data index which we're about to write. All other data will be aggregated until it can be written out
        # in the appropriate order
        self._nextDataIndex = 0

        # the aggregation is a simple map between indices and strings
        self._dataLeftForWriting = {}

        # write header
        if openas == 'w':
            with open(filename, openas) as file:
                file.write(headerToWrite)


    def Write(self, strToWrite, dataIndex, lock = None):
        """ Attempts to write out the data in an ordered fashion. If the data at this index can not be written
            immediately, we store the data to be processed later (at the next request).

            :param strToWrite:
            :param dataIndex:
            :param lock: lock to protect parallel writer (needs to be shared by Pool objects)
        """
        if lock is not None:
            lock.acquire()

        # let's make sure we save a whole bunch of data before trying to drain the queue
        if len(self._dataLeftForWriting) < 10:
            self._dataLeftForWriting[dataIndex] = strToWrite
            if lock is not None:
                lock.release()
            return

        with open(self._fileName, 'a') as file:
            # can we write out the data immediately?
            if self._nextDataIndex == dataIndex:
                file.write(strToWrite)
                self._nextDataIndex += 1
            # if not, add this data to the dictionary
            else:
                self._dataLeftForWriting[dataIndex] = strToWrite

            # try writing out other indexes
            while len(self._dataLeftForWriting) > 0 and \
                  self._nextDataIndex in self._dataLeftForWriting:
                str = self._dataLeftForWriting[self._nextDataIndex]
                file.write(str)
                self._dataLeftForWriting.pop(self._nextDataIndex)
                self._nextDataIndex += 1

        if lock is not None:
            lock.release()


    def FlushWritingToFile(self):
        with open(self._fileName, 'a') as file:
            i = 0
            while len(self._dataLeftForWriting) > 0:
                if i in self._dataLeftForWriting:
                    file.write(self._dataLeftForWriting[i])
                    self._dataLeftForWriting.pop(i)
                i += 1

