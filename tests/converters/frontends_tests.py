import itertools
import os
import unittest

import mido  # type: ignore
import numpy as np  # type: ignore

from mutwo import core_events
from mutwo import core_parameters
from mutwo import core_utilities
from mutwo import music_events
from mutwo import music_parameters
from mutwo import midi_converters


class CentDeviationToPitchBendingNumberTest(unittest.TestCase):
    def setUp(cls):
        cls.converter0 = midi_converters.CentDeviationToPitchBendingNumber(
            maximum_pitch_bend_deviation=200
        )
        cls.converter1 = midi_converters.CentDeviationToPitchBendingNumber(
            maximum_pitch_bend_deviation=500
        )

    def test_cent_deviation_to_pitch_bending_number(self):
        # first test all 'border values'
        self.assertEqual(self.converter0.convert(0), 0)
        self.assertEqual(
            self.converter0.convert(200),
            midi_converters.constants.NEUTRAL_PITCH_BEND,
        )
        self.assertEqual(
            self.converter0.convert(-200),
            -midi_converters.constants.NEUTRAL_PITCH_BEND,
        )
        self.assertEqual(
            self.converter1.convert(-500),
            -midi_converters.constants.NEUTRAL_PITCH_BEND,
        )
        self.assertEqual(
            self.converter1.convert(5000),
            midi_converters.constants.NEUTRAL_PITCH_BEND,
        )

        # test too high / too low values
        self.assertEqual(
            self.converter0.convert(250),
            midi_converters.constants.NEUTRAL_PITCH_BEND,
        )
        self.assertEqual(
            self.converter0.convert(-250),
            -midi_converters.constants.NEUTRAL_PITCH_BEND,
        )

        # now test values inbetween
        self.assertTrue(
            self.converter0.convert(100)
            - int(midi_converters.constants.NEUTRAL_PITCH_BEND * 0.5)
            <= 1
        )
        self.assertEqual(
            self.converter0.convert(200 * 0.3),
            int(midi_converters.constants.NEUTRAL_PITCH_BEND * 0.3),
        )


class MutwoPitchToMidiPitchTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.converter = midi_converters.MutwoPitchToMidiPitch()

    def test_convert(self):
        pitch_to_tune_per_test = (
            music_parameters.WesternPitch("c", 4),
            music_parameters.WesternPitch("c", 4),
            music_parameters.WesternPitch("c", 4),
            music_parameters.WesternPitch("a", 4),
            music_parameters.WesternPitch("c", 3),
            music_parameters.WesternPitch("cqs", 3),
            music_parameters.WesternPitch("cqf", 3),
            music_parameters.WesternPitch("ces", 4),
        )
        expected_midi_data_per_test = (
            # expected midi note, expected pitch bending
            (60, 0),
            (60, 0),
            (60, 0),
            (69, 0),
            (48, 0),
            (48, round(midi_converters.constants.NEUTRAL_PITCH_BEND * 0.25)),
            (47, round(midi_converters.constants.NEUTRAL_PITCH_BEND * 0.25)),
            (60, round(midi_converters.constants.NEUTRAL_PITCH_BEND * 0.125)),
        )
        for pitch_to_tune, expected_midi_data in zip(
            pitch_to_tune_per_test, expected_midi_data_per_test
        ):
            self.assertEqual(self.converter.convert(pitch_to_tune), expected_midi_data)


class EventToMidiFileTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.midi_file_path = "tests/converters/test.mid"
        cls.converter = midi_converters.EventToMidiFile()
        cls.sequential_event = core_events.SequentialEvent(
            [
                music_events.NoteLike(music_parameters.WesternPitch(pitch), 1, 1)
                for pitch in "c d e f g a b a g f e d c".split(" ")
            ]
        )
        cls.simultaneous_event = core_events.SimultaneousEvent(
            [cls.sequential_event, cls.sequential_event]
        )

    # ########################################################### #
    # tests to make sure that the methods return the expected     #
    # results.                                                    #
    # ########################################################### #

    def test_assert_midi_file_type_has_correct_type(self):
        for wrong_midi_file_type in (
            "hi",
            2,
            100,
            -10,
            1.3,
            music_parameters.WesternPitch(),
        ):
            self.assertRaises(
                ValueError,
                lambda: self.converter._assert_midi_file_type_has_correct_value(
                    wrong_midi_file_type
                ),
            )

    def test_assert_available_midi_channels_have_correct_value(self):
        for problematic_available_midi_channel_tuple in (
            (0, 14, 19),
            (100,),
            ("hi", 12),
        ):
            self.assertRaises(
                ValueError,
                lambda: self.converter._assert_available_midi_channel_tuple_has_correct_value(
                    problematic_available_midi_channel_tuple
                ),
            )

    def test_beats_per_minute_to_beat_length_in_microseconds(self):
        for bpm, beat_length_in_microseconds in (
            # bpm 60 should take one second per beat
            (60, 1000000),
            (30, 2000000),
            (120, 500000),
        ):
            self.assertEqual(
                self.converter._beats_per_minute_to_beat_length_in_microseconds(bpm),
                beat_length_in_microseconds,
            )

    def test_adjust_beat_length_in_microseconds(self):
        # should return the same number
        tempo_point = 40
        beat_length_in_microseconds = mido.bpm2tempo(tempo_point)
        self.assertEqual(
            midi_converters.EventToMidiFile._adjust_beat_length_in_microseconds(
                tempo_point, beat_length_in_microseconds
            ),
            beat_length_in_microseconds,
        )

        # should return MAXIMUM_MICROSECONDS_PER_BEAT, because bpm 3
        # is already too slow
        tempo_point = 3
        beat_length_in_microseconds = mido.bpm2tempo(tempo_point)
        self.assertEqual(
            midi_converters.EventToMidiFile._adjust_beat_length_in_microseconds(
                tempo_point, beat_length_in_microseconds
            ),
            midi_converters.constants.MAXIMUM_MICROSECONDS_PER_BEAT,
        )

    def test_find_available_midi_channel_tuple(self):
        converter0 = midi_converters.EventToMidiFile()
        converter1 = midi_converters.EventToMidiFile(
            distribute_midi_channels=True, midi_channel_count_per_track=1
        )

        n_sequential_events = 17
        simultaneous_event = core_events.SimultaneousEvent(
            [
                core_events.SequentialEvent([music_events.NoteLike([], 2, 1)])
                for _ in range(n_sequential_events)
            ]
        )

        self.assertEqual(
            converter0._find_available_midi_channel_tuple_per_sequential_event(
                simultaneous_event
            ),
            tuple(
                midi_converters.configurations.DEFAULT_AVAILABLE_MIDI_CHANNEL_TUPLE
                for _ in range(n_sequential_events)
            ),
        )

        self.assertEqual(
            converter1._find_available_midi_channel_tuple_per_sequential_event(
                simultaneous_event
            ),
            tuple(
                (
                    nth_channel
                    % len(midi_converters.constants.ALLOWED_MIDI_CHANNEL_TUPLE),
                )
                for nth_channel in range(n_sequential_events)
            ),
        )

    def test_beats_to_ticks(self):
        converter0 = midi_converters.EventToMidiFile()
        converter1 = midi_converters.EventToMidiFile(ticks_per_beat=100)
        converter2 = midi_converters.EventToMidiFile(ticks_per_beat=1000)

        n_beats_collection = (10, 30, 31.12, 11231.5523)

        for converter in (converter0, converter1, converter2):
            for n_beats in n_beats_collection:
                self.assertEqual(
                    converter._beats_to_ticks(n_beats),
                    int(converter._ticks_per_beat * n_beats),
                )

    def test_tempo_envelope_to_midi_messages(self):
        tempo_envelope = core_events.TempoEnvelope(
            ((0, 60), (2, 60), (2, 40), (5, 40), (5, 100))
        )
        midi_message_tuple = tuple(
            mido.MetaMessage(
                "set_tempo",
                tempo=self.converter._beats_per_minute_to_beat_length_in_microseconds(
                    level
                ),
                time=absolute_time.duration_in_floats
                * midi_converters.configurations.DEFAULT_TICKS_PER_BEAT,
            )
            for absolute_time, level in zip(
                core_utilities.accumulate_from_n(
                    tempo_envelope.get_parameter("duration"),
                    core_parameters.DirectDuration(0),
                ),
                tempo_envelope.value_tuple,
            )
        )

        self.assertEqual(
            self.converter._tempo_envelope_to_midi_message_tuple(tempo_envelope),
            midi_message_tuple,
        )

    def test_note_information_to_midi_messages(self):
        # loop only channel 0
        midi_channel = 0
        available_midi_channels_cycle = itertools.cycle((midi_channel,))
        for note_information in (
            (0, 100, 127, music_parameters.WesternPitch("c", 4)),
            (200, 300, 0, music_parameters.WesternPitch("ds", 3)),
            (121, 122, 42, music_parameters.JustIntonationPitch("7/4")),
            (101221, 120122, 100, music_parameters.DirectPitch(443)),
            (12, 14, 122, music_parameters.DirectPitch(2)),
        ):
            start, end, velocity, pitch = note_information

            midi_pitch, pitch_bending_message_tuple = self.converter._tune_pitch(
                start, end, pitch, midi_channel
            )
            note_on_message = mido.Message(
                "note_on",
                note=midi_pitch,
                velocity=velocity,
                time=start,
                channel=midi_channel,
            )
            note_off_message = mido.Message(
                "note_off",
                note=midi_pitch,
                velocity=velocity,
                time=end,
                channel=midi_channel,
            )
            expected_midi_message_tuple = pitch_bending_message_tuple + (
                note_on_message,
                note_off_message,
            )

            self.assertEqual(
                self.converter._note_information_to_midi_message_tuple(
                    start, end, velocity, pitch, next(available_midi_channels_cycle)
                ),
                expected_midi_message_tuple,
            )

    def test_extracted_data_to_midi_message_tuple(self):
        # TODO(is this really a test (just using the same code or code structure
        # that is used in the tested method)?)

        # loop only channel 0
        midi_channel = 0
        available_midi_channels_cycle = itertools.cycle((midi_channel,))
        for extracted_data in (
            (
                0,
                10,
                (music_parameters.WesternPitch("c", 4),),
                music_parameters.DecibelVolume(0),
                tuple([]),
            ),
            (
                101,
                232,
                (
                    music_parameters.WesternPitch("ds", 2),
                    music_parameters.JustIntonationPitch("3/7"),
                ),
                music_parameters.DirectVolume(0.1212),
                (mido.Message("control_change", channel=0, value=100, time=22),),
            ),
        ):
            (
                absolute_time,
                duration,
                pitch_list,
                volume,
                control_messages,
            ) = extracted_data
            start = self.converter._beats_to_ticks(absolute_time)
            end = self.converter._beats_to_ticks(duration) + start
            velocity = volume.midi_velocity
            expected_midi_messages = list(control_messages)
            for control_message in expected_midi_messages:
                control_message.time = start

            for pitch in pitch_list:
                expected_midi_messages.extend(
                    self.converter._note_information_to_midi_message_tuple(
                        start, end, velocity, pitch, next(available_midi_channels_cycle)
                    )
                )

            self.assertEqual(
                self.converter._extracted_data_to_midi_message_tuple(
                    absolute_time,
                    duration,
                    available_midi_channels_cycle,
                    pitch_list,
                    volume,
                    control_messages,
                ),
                tuple(expected_midi_messages),
            )

    def test_tune_pitch(self):
        midi_channel = 1
        absolute_tick_start = 20
        self.assertEqual(
            (
                69,
                (
                    mido.Message(
                        "pitchwheel",
                        channel=midi_channel,
                        pitch=0,
                        # mutwo will try to put the
                        # pitch bending message one tick
                        # earlier
                        time=absolute_tick_start - 1,
                    ),
                ),
            ),
            self.converter._tune_pitch(
                absolute_tick_start,
                100,
                music_parameters.DirectPitch(440),
                midi_channel,
            ),
        )

    def test_tune_pitch_with_microtone_up(self):
        midi_channel = 1
        self.assertEqual(
            (
                69,
                (mido.Message("pitchwheel", channel=midi_channel, pitch=2048, time=0),),
            ),
            self.converter._tune_pitch(
                0, 100, music_parameters.WesternPitch("aqs"), midi_channel
            ),
        )

    def test_tune_pitch_with_microtone_down(self):
        midi_channel = 1
        self.assertEqual(
            (
                69,
                (
                    mido.Message(
                        "pitchwheel", channel=midi_channel, pitch=-1024, time=0
                    ),
                ),
            ),
            self.converter._tune_pitch(
                0, 100, music_parameters.WesternPitch("aef"), midi_channel
            ),
        )

    def test_tune_pitch_with_constant_envelope(self):
        midi_channel = 1
        pitch = music_parameters.DirectPitch(440)
        pitch.envelope[:] = [
            core_events.SimpleEvent(100).set_parameter(
                "pitch_interval", music_parameters.DirectPitchInterval(-200)
            ),
            core_events.SimpleEvent(0).set_parameter(
                "pitch_interval", music_parameters.DirectPitchInterval(200)
            ),
        ]
        absolute_tick_start = 1000
        n_ticks = 100

        pitchwheel_message_list = []
        for tick, tick_percentage in enumerate(np.linspace(0, 1, n_ticks, dtype=float)):
            pitch_bend = (
                int(tick_percentage * midi_converters.constants.MAXIMUM_PITCH_BEND)
                - midi_converters.constants.NEUTRAL_PITCH_BEND
            )
            pitchwheel_message = mido.Message(
                "pitchwheel",
                channel=midi_channel,
                pitch=pitch_bend,
                time=tick + absolute_tick_start,
            )
            pitchwheel_message_list.append(pitchwheel_message)

        result_midi_pitch, result_pitchwheel_message_tuple = self.converter._tune_pitch(
            absolute_tick_start, absolute_tick_start + n_ticks, pitch, midi_channel
        )
        self.assertEqual(result_midi_pitch, 69)

        for result_pitchwheel_message, expected_pitchwheel_message in zip(
            result_pitchwheel_message_tuple, pitchwheel_message_list
        ):
            # compare pitch
            # Allow rounding error of 0.0244140625 cents (for maximum_pitch_bend = 200 cents)
            self.assertTrue(
                abs(result_pitchwheel_message.pitch - expected_pitchwheel_message.pitch)  # type: ignore
                <= 1
            )
            # compare time
            self.assertEqual(
                result_pitchwheel_message.time,  # type: ignore
                expected_pitchwheel_message.time,  # type: ignore
            )

    def test_tune_pitch_with_centering_envelope(self):
        n_ticks = 1000
        midi_channel = 1
        pitch = music_parameters.DirectPitch(440)
        pitch.envelope[:] = [
            core_events.SimpleEvent(n_ticks / 2).set_parameter(
                "pitch_interval", music_parameters.DirectPitchInterval(-200)
            ),
            core_events.SimpleEvent(n_ticks / 2).set_parameter(
                "pitch_interval", music_parameters.DirectPitchInterval(0)
            ),
        ]

        pitchwheel_message_list = []
        for tick, tick_percentage in enumerate(
            np.linspace(0.25, 0.75, n_ticks // 2, dtype=float)
        ):
            pitch_bend = (
                int(midi_converters.constants.MAXIMUM_PITCH_BEND * tick_percentage)
                - midi_converters.constants.NEUTRAL_PITCH_BEND
            )
            pitchwheel_message = mido.Message(
                "pitchwheel", channel=midi_channel, pitch=pitch_bend, time=tick
            )
            pitchwheel_message_list.append(pitchwheel_message)

        time_offset = pitchwheel_message_list[-1].time

        for nth_tick in range((n_ticks // 2) + 1):
            pitchwheel_message = mido.Message(
                "pitchwheel",
                channel=midi_channel,
                pitch=4095,
                time=nth_tick + time_offset + 1,
            )
            pitchwheel_message_list.append(pitchwheel_message)

        result_midi_pitch, result_pitchwheel_message_tuple = self.converter._tune_pitch(
            0, n_ticks, pitch, midi_channel
        )
        self.assertEqual(result_midi_pitch, 68)

        for result_pitchwheel_message, expected_pitchwheel_message in zip(
            result_pitchwheel_message_tuple, pitchwheel_message_list
        ):
            # compare pitch
            # Allow rounding error of 0.244140625 cents (for maximum_pitch_bend = 200 cents)
            self.assertTrue(
                abs(result_pitchwheel_message.pitch - expected_pitchwheel_message.pitch)  # type: ignore
                <= 10
            )
            # compare time
            self.assertEqual(
                result_pitchwheel_message.time,  # type: ignore
                expected_pitchwheel_message.time,  # type: ignore
            )

    def test_simple_event_to_midi_message_tuple(self):
        # loop only channel 2
        midi_channel = 2
        available_midi_channels_cycle = itertools.cycle((midi_channel,))

        # ########################### #
        #         test a rest         #
        # ########################### #

        # a rest shouldn't produce any messages
        rest = core_events.SimpleEvent(2)
        self.assertEqual(
            self.converter._simple_event_to_midi_message_tuple(
                rest, 0, available_midi_channels_cycle
            ),
            tuple([]),
        )

        # ########################### #
        #         test a tone         #
        # ########################### #

        tone = music_events.NoteLike(music_parameters.WesternPitch("c", 4), 2, 1)
        absolute_time1 = 32
        absolute_time1_in_ticks = self.converter._beats_to_ticks(absolute_time1)
        self.assertEqual(
            self.converter._simple_event_to_midi_message_tuple(
                tone, absolute_time1, available_midi_channels_cycle
            ),
            (
                mido.Message(
                    "pitchwheel",
                    channel=midi_channel,
                    pitch=0,
                    time=absolute_time1_in_ticks - 1,
                ),
                mido.Message(
                    "note_on",
                    note=60,
                    velocity=127,
                    time=absolute_time1_in_ticks,
                    channel=midi_channel,
                ),
                mido.Message(
                    "note_off",
                    note=60,
                    velocity=127,
                    time=absolute_time1_in_ticks
                    + self.converter._beats_to_ticks(tone.duration),
                    channel=midi_channel,
                ),
            ),
        )

        # ########################### #
        #         test a chord        #
        # ########################### #

        # use two different channels
        midi_channels = 2, 3
        available_midi_channels_cycle = itertools.cycle(midi_channels)

        chord = music_events.NoteLike(
            [
                music_parameters.WesternPitch("c", 4),
                music_parameters.WesternPitch("aqs", 4),
            ],
            2,
            0.5,
        )
        absolute_time2 = 2
        absolute_time2_in_ticks = self.converter._beats_to_ticks(absolute_time2)
        self.assertEqual(
            self.converter._simple_event_to_midi_message_tuple(
                chord, absolute_time2, available_midi_channels_cycle
            ),
            (
                mido.Message(
                    "pitchwheel",
                    channel=midi_channels[0],
                    pitch=0,
                    time=absolute_time2_in_ticks - 1,
                ),
                mido.Message(
                    "note_on",
                    note=60,
                    velocity=107,
                    time=absolute_time2_in_ticks,
                    channel=midi_channels[0],
                ),
                mido.Message(
                    "note_off",
                    note=60,
                    velocity=107,
                    time=absolute_time2_in_ticks
                    + self.converter._beats_to_ticks(tone.duration),
                    channel=midi_channels[0],
                ),
                mido.Message(
                    "pitchwheel",
                    channel=midi_channels[1],
                    pitch=2048,
                    time=absolute_time2_in_ticks - 1,
                ),
                mido.Message(
                    "note_on",
                    note=69,
                    velocity=107,
                    time=absolute_time2_in_ticks,
                    channel=midi_channels[1],
                ),
                mido.Message(
                    "note_off",
                    note=69,
                    velocity=107,
                    time=absolute_time2_in_ticks
                    + self.converter._beats_to_ticks(tone.duration),
                    channel=midi_channels[1],
                ),
            ),
        )

    def test_sequential_event_to_midi_message_tuple(self):
        pass

    def test_midi_message_tuple_to_midi_track(self):
        pass

    def test_add_simple_event_to_midi_file(self):
        pass

    def test_add_sequential_event_to_midi_file(self):
        pass

    def test_add_simultaneous_event_to_midi_file(self):
        pass

    def test_event_to_midi_file(self):
        pass

    # ########################################################### #
    # tests to make sure that the different init arguments do     #
    # work correctly                                              #
    # ########################################################### #

    def test_correct_midi_file_type(self):
        # make sure generated midi file has the correct midi file type

        converter0 = midi_converters.EventToMidiFile(midi_file_type=0)
        converter1 = midi_converters.EventToMidiFile(midi_file_type=1)

        for converter in (converter0, converter1):
            for event in (self.sequential_event, self.simultaneous_event):
                converter.convert(event, self.midi_file_path)
                midi_file = mido.MidiFile(self.midi_file_path)
                self.assertEqual(midi_file.type, converter._midi_file_type)
                os.remove(self.midi_file_path)

    def test_overriding_simple_event_to_arguments(self):
        # make sure generated midi file has the correct midi file type

        constant_pitch = music_parameters.WesternPitch("c")
        constant_volume = music_parameters.DirectVolume(1)
        constant_control_message = mido.Message("control_change", value=100)
        converter = midi_converters.EventToMidiFile(
            simple_event_to_pitch_list=lambda event: (constant_pitch,),
            simple_event_to_volume=lambda event: constant_volume,
            simple_event_to_control_message_tuple=lambda event: (
                constant_control_message,
            ),
        )

        converter.convert(self.sequential_event, self.midi_file_path)
        midi_file = mido.MidiFile(self.midi_file_path)
        control_message_index = 0
        note_on_message_index = 0
        for message in midi_file:
            if message.type == "note_on":
                self.assertAlmostEqual(message.note, constant_pitch.midi_pitch_number)
                self.assertEqual(
                    message.velocity,
                    constant_volume.midi_velocity,
                )
                note_on_message_index += 1
            elif message.type == "control_change":
                self.assertEqual(message.value, constant_control_message.value)
                control_message_index += 1

        self.assertEqual(note_on_message_index, len(self.sequential_event))
        self.assertEqual(control_message_index, len(self.sequential_event))

        os.remove(self.midi_file_path)

    def test_available_midi_channel_tuple_argument(self):
        # make sure mutwo only writes notes to midi channel that are
        # available and furthermore cycles through all available midi
        # channels!

        for available_midi_channel_tuple in (
            (0,),
            (0, 1, 2, 3),
            (0, 3, 4),
            (
                2,
                11,
            ),
        ):
            converter = midi_converters.EventToMidiFile(
                available_midi_channel_tuple=available_midi_channel_tuple
            )
            converter.convert(self.sequential_event, self.midi_file_path)
            midi_file = mido.MidiFile(self.midi_file_path)
            available_midi_channel_cycle = itertools.cycle(available_midi_channel_tuple)
            for message in midi_file:
                if message.type == "note_on":
                    self.assertEqual(
                        message.channel, next(available_midi_channel_cycle)
                    )
            os.remove(self.midi_file_path)

    def test_distribute_midi_channels_argument(self):
        # makes sure mutwo distributes midi channels on different
        # sequential events according to the behaviour that is written
        # in the EventToMidiFile docstring

        pass


if __name__ == "__main__":
    unittest.main()
