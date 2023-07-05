import unittest

class BaseTest(unittest.TestCase):

    def setUp(self):
        print(f'\n{__name__} : {self._testMethodName}  ', end=' ')
    
