# Twisted, the Framework of Your Internet
# Copyright (C) 2001 Matthew W. Lefkowitz
#
# This library is free software; you can redistribute it and/or
# modify it under the terms of version 2.1 of the GNU Lesser General Public
# License as published by the Free Software Foundation.
#
# This library is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU
# Lesser General Public License for more details.
#
# You should have received a copy of the GNU Lesser General Public
# License along with this library; if not, write to the Free Software
# Foundation, Inc., 59 Temple Place, Suite 330, Boston, MA  02111-1307  USA

"""
This module provides support for Twisted to interact with the PyQt mainloop.

In order to use this support, simply do the following::

    |  from twisted.internet import qternet
    |  qternet.install()

Then use twisted.internet APIs as usual.  The other methods here are not
intended to be called directly.
"""

__all__ = ['install']

# System Imports
from qt import QSocketNotifier, QObject, SIGNAL, QTimer

# Twisted Imports
from twisted.python import log

# Sibling Imports
import main, default

reads = default.reads
writes = default.writes
delayeds = main.delayeds
hasReader = reads.has_key
hasWriter = writes.has_key


class TwistedSocketNotifier(QSocketNotifier):
    '''Connection between an fd event and reader/writer callbacks'''

    def __init__(self, watcher, type):
        QSocketNotifier.__init__(self, watcher.fileno(), type)
        self.watcher = watcher
        self.fn = None
        if type == QSocketNotifier.Read:
            self.fn = self.read
        elif type == QSocketNotifier.Write:
            self.fn = self.write
        QObject.connect( self, SIGNAL("activated(int)"), self.fn )

    def shutdown(self):
        self.setEnabled(0)
        QObject.disconnect(self, SIGNAL("activated(int)"), self.fn)
        self.fn = self.watcher = None

    def read(self, sock):
        why = None
        w = self.watcher
        try:
            why = w.doRead()
        except:
            why = main.CONNECTION_LOST
            log.msg('Error in %s.doRead()' % w)
            log.deferr()
        if why:
            try:
                w.connectionLost()
            except:
                log.deferr()
            removeReader(w)
            removeWriter(w)
        simulate()

    def write(self, sock):
        why = None
        w = self.watcher
        self.setEnabled(0)
        try:
            why = w.doWrite()
        except:
            why = main.CONNECTION_LOST
            log.msg('Error in %s.doWrite()' % w)
            log.deferr()
        if why:
            try:
                w.connectionLost()
            except:
                log.deferr()
            removeReader(w)
            removeWriter(w)
        else:
            self.setEnabled(1)
        simulate()


# global timer
_timer = None


class QTReactor(default.ReactorBase):
    """Qt based reactor."""

    def addReader(self, reader):
        if not hasReader(reader):
            reads[reader] = TwistedSocketNotifier(reader, QSocketNotifier.Read)

    def addWriter(self, writer):
        if not hasWriter(writer):
            writes[writer] = TwistedSocketNotifier(writer, QSocketNotifier.Write)

    def removeReader(self, reader): 
        if hasReader(reader):
            reads[reader].shutdown()
            del reads[reader]

    def removeWriter(self, writer): 
        if hasWriter(writer):
            writes[writer].shutdown()
            del writes[writer]

    def simulate(self):
        global _timer
        if _timer: _timer.stop()

        timeout = (main.runUntilCurrent() or 0.1) * 1010

        if not _timer:
            _timer = QTimer()
            QObject.connect( _timer, SIGNAL("timeout()"), self.simulate )
        _timer.start(timeout, 1)

    def cleanup(self):
        global _timer
        if _timer: 
            _timer.stop()
            _timer = None


def install():
    """Configure the twisted mainloop to be run inside the qt mainloop.
    """
    reactor = QTReactor()
    reactor.install()
    main.callBeforeShutdown( reactor.cleanup )

    main.running = 2
    main.ALLOW_TWISTED_REBUILD = 0
    reactor.simulate()
