import unittest

class BaseTest(unittest.TestCase):

    def setUp(self):
        print(f'\n{self.__class__.__module__} : {self._testMethodName}  ', end=' ')
