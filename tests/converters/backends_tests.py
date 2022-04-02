import unittest

import mido

from mutwo import core_events
from mutwo import midi_converters
from mutwo import music_events
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
    def setUp(self):
        self.midi_file_to_event = midi_converters.MidiFileToEvent()

    # ###################################################################### #
    #                    test static methods                                 #
    # ###################################################################### #

    def test_tick_to_duration(self):
        self.assertEqual(self.midi_file_to_event._tick_to_duration(1024, 1024), 1)
        self.assertEqual(self.midi_file_to_event._tick_to_duration(1024, 512), 2)
        self.assertEqual(self.midi_file_to_event._tick_to_duration(30, 10), 3)
        self.assertEqual(self.midi_file_to_event._tick_to_duration(5, 10), 0.5)

    def test_add_simple_event_to_sequential_event(self):
        sequential_event0 = core_events.SequentialEvent([])
        self.midi_file_to_event._add_simple_event_to_sequential_event(
            sequential_event0, 0, core_events.SimpleEvent(10)
        )
        self.assertEqual(
            sequential_event0,
            core_events.SequentialEvent([core_events.SimpleEvent(10)]),
        )
        sequential_event1 = core_events.SequentialEvent([])
        self.midi_file_to_event._add_simple_event_to_sequential_event(
            sequential_event1, 5, core_events.SimpleEvent(10)
        )
        self.assertEqual(
            sequential_event1,
            core_events.SequentialEvent(
                [core_events.SimpleEvent(5), core_events.SimpleEvent(10)]
            ),
        )

    def test_note_pair_tuple_to_start_and_stop_tuple_to_note_pair_list(self):
        note_pair_tuple = (
            (
                mido.Message("note_on", note=60, velocity=100, time=100),
                mido.Message("note_off", note=60, velocity=100, time=200),
            ),
            (
                mido.Message("note_on", note=65, velocity=100, time=100),
                mido.Message("note_off", note=65, velocity=100, time=200),
            ),
            (
                mido.Message("note_on", note=65, velocity=100, time=120),
                mido.Message("note_off", note=65, velocity=100, time=200),
            ),
        )

        self.assertEqual(
            self.midi_file_to_event._note_pair_tuple_to_start_and_stop_tuple_to_note_pair_list(
                note_pair_tuple
            ),
            {
                (100, 200): [
                    (
                        mido.Message("note_on", note=60, velocity=100, time=100),
                        mido.Message("note_off", note=60, velocity=100, time=200),
                    ),
                    (
                        mido.Message("note_on", note=65, velocity=100, time=100),
                        mido.Message("note_off", note=65, velocity=100, time=200),
                    ),
                ],
                (120, 200): [
                    (
                        mido.Message("note_on", note=65, velocity=100, time=120),
                        mido.Message("note_off", note=65, velocity=100, time=200),
                    ),
                ],
            },
        )

    def test_get_note_pair_tuple(self):
        note_on_message_list = [
            mido.Message("note_on", note=60, velocity=100, channel=0, time=30),
            mido.Message("note_on", note=60, velocity=100, channel=1, time=50),
            mido.Message("note_on", note=60, velocity=100, channel=1, time=70),
            mido.Message("note_on", note=62, velocity=100, channel=1, time=90),
        ]
        note_off_message_list = [
            mido.Message("note_off", note=60, velocity=0, channel=1, time=60),
            mido.Message("note_off", note=60, velocity=0, channel=0, time=65),
            mido.Message("note_off", note=62, velocity=0, channel=1, time=100),
            mido.Message("note_off", note=60, velocity=0, channel=1, time=105),
        ]

        note_pair_tuple = (
            (
                mido.Message("note_on", note=60, velocity=100, channel=0, time=30),
                mido.Message("note_off", note=60, velocity=0, channel=0, time=65),
            ),
            (
                mido.Message("note_on", note=60, velocity=100, channel=1, time=50),
                mido.Message("note_off", note=60, velocity=0, channel=1, time=60),
            ),
            (
                mido.Message("note_on", note=60, velocity=100, channel=1, time=70),
                mido.Message("note_off", note=60, velocity=0, channel=1, time=105),
            ),
            (
                mido.Message("note_on", note=62, velocity=100, channel=1, time=90),
                mido.Message("note_off", note=62, velocity=0, channel=1, time=100),
            ),
        )

        self.assertEqual(
            self.midi_file_to_event._get_note_pair_tuple(
                {"note_on": note_on_message_list, "note_off": note_off_message_list}
            ),
            note_pair_tuple,
        )

    def test_get_note_off_partner(self):
        self.assertEqual(
            self.midi_file_to_event._get_note_off_partner(
                mido.Message("note_on", note=60, channel=0, velocity=100, time=50),
                [
                    mido.Message("note_off", note=60, channel=0, velocity=0, time=30),
                    mido.Message("note_off", note=60, channel=1, velocity=0, time=60),
                    mido.Message("note_off", note=61, channel=0, velocity=0, time=80),
                ],
            ),
            None,
        )
        self.assertEqual(
            self.midi_file_to_event._get_note_off_partner(
                mido.Message("note_on", note=60, channel=0, velocity=100, time=50),
                [
                    mido.Message("note_off", note=60, channel=0, velocity=0, time=30),
                    mido.Message("note_off", note=60, channel=1, velocity=0, time=60),
                    mido.Message("note_off", note=60, channel=0, velocity=0, time=80),
                ],
            ),
            mido.Message("note_off", note=60, channel=0, velocity=0, time=80),
        )

    def test_get_message_type_to_midi_message_list(self):
        self.assertEqual(
            self.midi_file_to_event._get_message_type_to_midi_message_list(
                mido.MidiFile(tracks=[mido.MidiTrack([])])
            ),
            {},
        )
        self.assertEqual(
            self.midi_file_to_event._get_message_type_to_midi_message_list(
                mido.MidiFile(
                    tracks=[
                        mido.MidiTrack(
                            [
                                mido.Message(
                                    "note_on", note=60, channel=10, velocity=11, time=0
                                ),
                                mido.Message(
                                    "note_on", note=62, channel=9, velocity=11, time=5
                                ),
                                mido.Message(
                                    "note_off", note=60, channel=9, velocity=0, time=10
                                ),
                                mido.Message(
                                    "note_off", note=60, channel=10, velocity=0, time=0
                                ),
                            ]
                        ),
                        mido.MidiTrack(
                            [
                                mido.Message(
                                    "note_on", note=60, channel=5, velocity=11, time=0
                                ),
                            ]
                        ),
                    ]
                )
            ),
            {
                "note_on": [
                    mido.Message("note_on", note=60, channel=10, velocity=11, time=0),
                    mido.Message("note_on", note=60, channel=5, velocity=11, time=0),
                    mido.Message("note_on", note=62, channel=9, velocity=11, time=5),
                ],
                "note_off": [
                    mido.Message("note_off", note=60, channel=9, velocity=0, time=15),
                    mido.Message("note_off", note=60, channel=10, velocity=0, time=15),
                ],
            },
        )

    # ###################################################################### #
    #                    test private methods                                #
    # ###################################################################### #

    def test_note_pair_list_to_simple_event(self):
        self.assertEqual(
            self.midi_file_to_event._note_pair_list_to_simple_event(
                [
                    (
                        mido.Message("note_on", note=69, velocity=127, time=0),
                        mido.Message("note_off", note=69, velocity=127, time=50),
                    )
                ],
                1,
            ),
            music_events.NoteLike(
                pitch_list=music_parameters.MidiPitch(69),
                volume="fffff",
                duration=50,
            ),
        )
        self.assertEqual(
            self.midi_file_to_event._note_pair_list_to_simple_event(
                [
                    (
                        mido.Message("note_on", note=69, velocity=127, time=0),
                        mido.Message("note_off", note=69, velocity=127, time=50),
                    )
                ],
                50,
            ),
            music_events.NoteLike(
                pitch_list=music_parameters.MidiPitch(69),
                volume="fffff",
                duration=1,
            ),
        )
        self.assertEqual(
            self.midi_file_to_event._note_pair_list_to_simple_event(
                [
                    (
                        mido.Message("note_on", note=69, velocity=1, time=20),
                        mido.Message("note_off", note=69, velocity=1, time=50),
                    ),
                    (
                        mido.Message("note_on", note=60, velocity=1, time=20),
                        mido.Message("note_off", note=60, velocity=1, time=50),
                    ),
                ],
                30,
            ),
            music_events.NoteLike(
                pitch_list=[
                    music_parameters.MidiPitch(69),
                    # Floating point error
                    music_parameters.MidiPitch(59.99999999999999),
                ],
                volume="ppppp",
                duration=1,
            ),
        )

    # ###################################################################### #
    #                    test public methods                                 #
    # ###################################################################### #

    def test_convert(self):
        midi_file_to_convert = mido.MidiFile(
            tracks=[
                mido.MidiTrack(
                    [
                        mido.Message("note_on", note=69, time=0, velocity=127),
                        mido.Message(
                            "note_on", note=69, time=0, velocity=127, channel=1
                        ),
                        mido.Message("note_off", note=69, time=10, velocity=127),
                        mido.Message(
                            "note_off", note=69, time=0, velocity=127, channel=1
                        ),
                        mido.Message("note_on", note=69, time=0, velocity=127),
                        mido.Message("note_off", note=69, time=20, velocity=127),
                    ]
                )
            ],
            ticks_per_beat=10,
        )
        self.assertEqual(
            self.midi_file_to_event.convert(midi_file_to_convert),
            core_events.SimultaneousEvent(
                [
                    core_events.SequentialEvent(
                        [
                            music_events.NoteLike(
                                pitch_list=[
                                    music_parameters.MidiPitch(69),
                                    music_parameters.MidiPitch(69),
                                ],
                                duration=1,
                                volume="fffff",
                            ),
                            music_events.NoteLike(
                                pitch_list=[music_parameters.MidiPitch(69)],
                                duration=2,
                                volume="fffff",
                            ),
                        ]
                    ),
                ]
            ),
        )


if __name__ == "__main__":
    unittest.main()
