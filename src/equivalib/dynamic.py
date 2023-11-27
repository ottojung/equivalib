## Copyright (C) 2023  Otto Jung
## This program is free software: you can redistribute it and/or modify it under the terms of the GNU General Public License as published by the Free Software Foundation; version 3 of the License. This program is distributed in the hope that it will be useful, but WITHOUT ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the GNU General Public License for more details. You should have received a copy of the GNU General Public License along with this program.  If not, see <http://www.gnu.org/licenses/>.

from contextlib import contextmanager

class DynamicEnvironment:
    def __init__(self):
        self.__dict__['assignments'] = {}


    def __getattr__(self, name):
        assignments = self.__dict__['assignments']
        if name in assignments:
            return assignments[name]
        raise AttributeError(f"no such variable in environment: '{name}'")


    @contextmanager
    def let(self, **kwargs):
        assignments = self.__dict__['assignments']
        old = {}
        for name, value in kwargs.items():
            old[name] = assignments.get(name, None)
            self.assignments[name] = value
        yield
        for name, value in old.items():
            assignments[name] = value


denv = DynamicEnvironment()
