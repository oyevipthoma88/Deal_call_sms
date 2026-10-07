import unittest
import bot

class SafetyTests(unittest.TestCase):
    def test_international_phone_validation(self):
        self.assertTrue(bot.PHONE_RE.fullmatch("+14155550123"))
        self.assertTrue(bot.PHONE_RE.fullmatch("919876543210"))
        self.assertFalse(bot.PHONE_RE.fullmatch("123"))
        self.assertFalse(bot.PHONE_RE.fullmatch("+0123456789"))
    def test_default_cap_is_bounded(self):
        self.assertGreaterEqual(bot.MAX_COUNT, 1)
        self.assertLessEqual(bot.MAX_COUNT, 100)

if __name__ == '__main__': unittest.main()
