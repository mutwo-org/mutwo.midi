import unittest

from mutwo import midi_converters
from mutwo import music_parameters


class PitchBendingNumberToDirectPitchIntervalTest(unittest.TestCase):
    def setUp(cls):
        cls.pitch_bending_number_to_direct_pitch_interval0 = (
            midi_converters.PitchBendingNumberToDirectPitchInterval(200)
        )
        cls.pitch_bending_number_to_direct_pitch_interval1 = (
            midi_converters.PitchBendingNumberToDirectPitchInterval(1200)
        )

    def test_convert(self):
        # First test all corner cases
        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval0.convert(0),
            music_parameters.DirectPitchInterval(0),
        )
        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval1.convert(0),
            music_parameters.DirectPitchInterval(0),
        )

        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval0.convert(8191),
            music_parameters.DirectPitchInterval(200),
        )
        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval1.convert(8191),
            music_parameters.DirectPitchInterval(1200),
        )

        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval0.convert(-8191),
            music_parameters.DirectPitchInterval(-200),
        )
        self.assertEqual(
            self.pitch_bending_number_to_direct_pitch_interval1.convert(-8191),
            music_parameters.DirectPitchInterval(-1200),
        )

        # Then test interpolations
        self.assertEqual(
            round(
                self.pitch_bending_number_to_direct_pitch_interval0.convert(
                    int(8191 // 2)
                ).cents
            ),
            100,
        )
        self.assertEqual(
            round(
                self.pitch_bending_number_to_direct_pitch_interval0.convert(
                    -int(8191 // 2)
                ).cents
            ),
            -100,
        )

        self.assertEqual(
            round(
                self.pitch_bending_number_to_direct_pitch_interval1.convert(
                    int(8191 // 2)
                ).cents
            ),
            600,
        )


class MidiPitchToMutwoPitchTest(object):
    def test_convert_for_type(self):
        """Ensure the resulting return type is correct"""

        self.assertEqual(
            type(self.midi_pitch_to_mutwo_pitch.convert((69, 0))),
            self.expected_pitch_type,
        )

    def test_convert_for_frequency(self):
        """Ensure the resulting frequency is correct"""

        self.assertAlmostEqual(
            self.midi_pitch_to_mutwo_pitch.convert((69, 0)).frequency,
            440,
        )
        self.assertAlmostEqual(
            self.midi_pitch_to_mutwo_pitch.convert((69 + 12, 0)).frequency,
            880,
        )
        self.assertAlmostEqual(
            self.midi_pitch_to_mutwo_pitch.convert((70, 0)).frequency, 466.164, delta=3
        )
        self.assertAlmostEqual(
            self.midi_pitch_to_mutwo_pitch.convert((69, int(8191 // 2))).frequency,
            466.164,
            delta=3,
        )


class MidiPitchToDirectPitchTest(unittest.TestCase, MidiPitchToMutwoPitchTest):
    def setUp(self):
        self.midi_pitch_to_mutwo_pitch = midi_converters.MidiPitchToDirectPitch()
        self.expected_pitch_type = music_parameters.DirectPitch


class MidiPitchToMutwoMidiPitchTest(unittest.TestCase, MidiPitchToMutwoPitchTest):
    def setUp(self):
        self.midi_pitch_to_mutwo_pitch = midi_converters.MidiPitchToMutwoMidiPitch()
        self.expected_pitch_type = music_parameters.MidiPitch


class MidiVelocityToWesternVolumeTest(unittest.TestCase):
    def setUp(self):
        self.midi_velocity_to_western_volume = (
            midi_converters.MidiVelocityToWesternVolume()
        )

    def test_convert(self):
        self.assertEqual(
            self.midi_velocity_to_western_volume.convert(127),
            music_parameters.WesternVolume("fffff"),
        )
        self.assertEqual(
            self.midi_velocity_to_western_volume.convert(0),
            music_parameters.WesternVolume("ppppp"),
        )
        self.assertEqual(
            self.midi_velocity_to_western_volume.convert(64),
            music_parameters.WesternVolume("mf"),
        )


class MidiFileToEventTest(unittest.TestCase):
    pass


if __name__ == "__main__":
    unittest.main()
