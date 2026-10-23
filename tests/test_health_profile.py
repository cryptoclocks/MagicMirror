import unittest
from health_profile import PULSE_BPM,RESPIRATIONS_PER_MINUTE,OXYGEN_PERCENT,TEMPERATURE_C,SLEEP_HOURS,SLEEP_GOAL_HOURS,cycle


class HealthProfileTests(unittest.TestCase):
    def test_demo_vitals_stay_in_adult_resting_reference_ranges(self):
        # References are recorded in HEALTH_DEMO.md. No clinical inference is performed.
        self.assertTrue(60<=PULSE_BPM<=100)
        self.assertTrue(12<=RESPIRATIONS_PER_MINUTE<=18)
        self.assertTrue(95<=OXYGEN_PERCENT<=100)
        self.assertTrue(36.5<=TEMPERATURE_C<=37.3)

    def test_animation_rates_share_the_numeric_profile(self):
        self.assertAlmostEqual(cycle(60,PULSE_BPM),PULSE_BPM)
        self.assertAlmostEqual(cycle(60,RESPIRATIONS_PER_MINUTE),RESPIRATIONS_PER_MINUTE)
        self.assertAlmostEqual(cycle(60/PULSE_BPM,PULSE_BPM),1)

    def test_sleep_is_explicitly_a_short_sleep_scenario(self):
        self.assertEqual(SLEEP_HOURS,5.5)
        self.assertLess(SLEEP_HOURS,SLEEP_GOAL_HOURS)
        self.assertEqual(SLEEP_GOAL_HOURS,7)


if __name__=='__main__':unittest.main()
