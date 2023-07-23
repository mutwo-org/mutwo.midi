"""Load midi files to mutwo"""

import abc
import copy
import typing

import mido
import numpy as np

try:
    import quicktions as fractions
except ImportError:
    import fractions

from mutwo import core_converters
from mutwo import core_events
from mutwo import core_parameters
from mutwo import core_utilities
from mutwo import midi_converters
from mutwo import music_converters
from mutwo import music_parameters

__all__ = (
    "PitchBendingNumberToPitchInterval",
    "PitchBendingNumberToDirectPitchInterval",
    "MidiPitchToMutwoPitch",
    "MidiPitchToDirectPitch",
    "MidiPitchToMutwoMidiPitch",
    "MidiVelocityToMutwoVolume",
    "MidiVelocityToWesternVolume",
    "MidiFileToEvent",
)


class PitchBendingNumberToPitchInterval(core_converters.abc.Converter):
    """Convert midi pitch bend number to :class:`mutwo.music_parameters.abc.PitchInterval`.

    :param maximum_pitch_bend_deviation: sets the maximum pitch bending range in cents.
        This value depends on the particular used software synthesizer and its settings,
        because it is up to the respective synthesizer how to interpret the pitch
        bending messages. By default mutwo sets the value to 200 cents which
        seems to be the most common interpretation among different manufacturers.
    :type maximum_pitch_bend_deviation: int
    """

    def __init__(self, maximum_pitch_bend_deviation: typing.Optional[float] = None):
        if maximum_pitch_bend_deviation is None:
            maximum_pitch_bend_deviation = (
                midi_converters.configurations.DEFAULT_MAXIMUM_PITCH_BEND_DEVIATION_IN_CENTS
            )

        self._maximum_pitch_bend_deviation = maximum_pitch_bend_deviation

    @abc.abstractmethod
    def convert(
        self,
        pitch_bending_number_to_convert: midi_converters.constants.PitchBend,
    ) -> music_parameters.abc.PitchInterval:
        ...


class PitchBendingNumberToDirectPitchInterval(PitchBendingNumberToPitchInterval):
    """Convert midi pitch bend number to :class:`mutwo.music_parameters.DirectPitchInterval`."""

    def convert(
        self,
        pitch_bending_number_to_convert: midi_converters.constants.PitchBend,
    ) -> music_parameters.DirectPitchInterval:
        """Convert pitch bending number to :class:`mutwo.music_parameters.DirectPitchInterval`

        :param pitch_bending_number_to_convert: The pitch bending number
            which shall be converted.
        :type pitch_bending_number_to_convert: midi_converters.constants.PitchBend
        """

        cent_deviation = core_utilities.scale(
            pitch_bending_number_to_convert,
            -midi_converters.constants.NEUTRAL_PITCH_BEND,
            midi_converters.constants.NEUTRAL_PITCH_BEND,
            -self._maximum_pitch_bend_deviation,
            self._maximum_pitch_bend_deviation,
        )

        return music_parameters.DirectPitchInterval(float(cent_deviation))


class MidiPitchToMutwoPitch(core_converters.abc.Converter):
    """Convert midi pitch to :class:`mutwo.music_parameters.abc.Pitch`.

    :param pitch_bending_number_to_pitch_interval: A callable object which
        transforms a pitch bending number (integer) to a
        :class:`mutwo.music_parameters.abc.PitchInterval`. Default to
        :class:`PitchBendingNumberToDirectPitchInterval`.
    :type pitch_bending_number_to_pitch_interval: typing.Callable[[midi_converters.constants.PitchBend], music_parameters.abc.PitchInterval]
    """

    def __init__(
        self,
        pitch_bending_number_to_pitch_interval: typing.Callable[
            [midi_converters.constants.PitchBend], music_parameters.abc.PitchInterval
        ] = PitchBendingNumberToDirectPitchInterval(),
    ):
        self._pitch_bending_number_to_pitch_interval = (
            pitch_bending_number_to_pitch_interval
        )

    @abc.abstractmethod
    def convert(
        self, midi_pitch_to_convert: midi_converters.constants.MidiPitch
    ) -> music_parameters.abc.Pitch:
        ...


class MidiPitchToDirectPitch(MidiPitchToMutwoPitch):
    def convert(
        self, midi_pitch_to_convert: midi_converters.constants.MidiPitch
    ) -> music_parameters.DirectPitch:
        midi_note, pitch_bend = midi_pitch_to_convert
        frequency = music_parameters.constants.MIDI_PITCH_FREQUENCY_TUPLE[midi_note]
        direct_pitch = music_parameters.DirectPitch(frequency)
        pitch_interval = self._pitch_bending_number_to_pitch_interval(pitch_bend)
        return direct_pitch.add(pitch_interval)


class MidiPitchToMutwoMidiPitch(MidiPitchToMutwoPitch):
    def convert(
        self, midi_pitch_to_convert: midi_converters.constants.MidiPitch
    ) -> music_parameters.MidiPitch:
        midi_note, pitch_bend = midi_pitch_to_convert
        midi_pitch = music_parameters.MidiPitch(midi_note)
        pitch_interval = self._pitch_bending_number_to_pitch_interval(pitch_bend)
        return midi_pitch.add(pitch_interval)


class MidiVelocityToMutwoVolume(core_converters.abc.Converter):
    """Convert midi velocity (integer) to :class:`mutwo.music_parameters.abc.Volume`."""

    @abc.abstractmethod
    def convert(
        self, midi_velocity: midi_converters.constants.MidiVelocity
    ) -> music_parameters.abc.Volume:
        ...


class MidiVelocityToWesternVolume(MidiVelocityToMutwoVolume):
    def convert(
        self, midi_velocity_to_convert: midi_converters.constants.MidiVelocity
    ) -> music_parameters.abc.Volume:
        """Convert midi velocity to :class:`mutwo.music_parameters.WesternVolume`

        :param midi_velocity_to_convert: The velocity which shall be converted.
        :type midi_velocity_to_convert: midi_converters.constants.MidiVelocity

        **Example:**

        >>> from mutwo import midi_converters
        >>> midi_converters.MidiVelocityToWesternVolume().convert(127)
        WesternVolume(fffff)
        >>> midi_converters.MidiVelocityToWesternVolume().convert(0)
        WesternVolume(ppppp)
        """

        standard_dynamic_indicator_count = len(
            music_parameters.constants.STANDARD_DYNAMIC_INDICATOR
        )
        dynamic_indicator_index = round(
            core_utilities.scale(
                midi_velocity_to_convert,
                music_parameters.constants.MINIMUM_VELOCITY,
                music_parameters.constants.MAXIMUM_VELOCITY,
                0,
                standard_dynamic_indicator_count - 1,
            )
        )
        dynamic_indicator = music_parameters.constants.STANDARD_DYNAMIC_INDICATOR[
            int(dynamic_indicator_index)
        ]
        return music_parameters.WesternVolume(dynamic_indicator)


MessageTypeToMidiMessageList = dict[str, list[mido.Message | mido.MetaMessage]]
NotePair = tuple[mido.Message, mido.Message]
NotePairTuple = tuple[NotePair, ...]
StartAndStopTupleToNotePairList = dict[tuple[int, int], list[NotePair]]


class MidiFileToEvent(core_converters.abc.Converter):
    """Convert a midi file to a mutwo event.

    :param mutwo_parameter_tuple_to_simple_event: A callable which converts a
        tuple of mutwo parameters (duration, pitch list, volume) to a
        :class:`mutwo.core_events.SimpleEvent`. In default state mutwo
         generates a :class:`mutwo.music_events.NoteLike`.
    :type mutwo_parameter_tuple_to_simple_event: typing.Callable[[tuple[core_constants.DurationType, music_parameters.abc.Pitch, music_parameters.abc.Volume]], core_events.SimpleEvent]
    :param midi_pitch_to_mutwo_pitch: Callable object which converts
        midi pitch (integer) to a :class:`mutwo.music_parameters.abc.Pitch`.
        Default to :class:`MidiPitchToMutwoMidiPitch`.
    :type midi_pitch_to_mutwo_pitch: typing.Callable[[midi_converters.constants.MidiPitch], music_parameters.abc.Pitch]
    :param midi_velocity_to_mutwo_volume: Callable object which converts
        midi velocity (integer) to a :class:`mutwo.music_parameters.abc.Voume`.
        Default to :class:`MidiPitchToWesternVolume`.
    :type midi_velocity_to_mutwo_volume: typing.Callable[[midi_converters.constants.MidiVelocity], music_parameters.abc.Volume]

    **Warning:**

    This is an unstable early version of the converter.
    Expect bugs when using it!

    **Disclaimer:**

    This conversion is incomplete: Not all information from a
    midi file will be used. In its current state the converter
    only takes into account midi notes (pitch, velocity and duration)
    and ignores all other midi messages.
    """

    def __init__(
        self,
        mutwo_parameter_dict_to_simple_event: typing.Callable[
            [core_converters.MutwoParameterDict],
            core_events.SimpleEvent,
        ] = music_converters.MutwoParameterDictToNoteLike(),
        midi_pitch_to_mutwo_pitch: typing.Callable[
            [midi_converters.constants.MidiPitch], music_parameters.abc.Pitch
        ] = MidiPitchToMutwoMidiPitch(),
        midi_velocity_to_mutwo_volume: typing.Callable[
            [midi_converters.constants.MidiVelocity], music_parameters.abc.Volume
        ] = MidiVelocityToWesternVolume(),
    ):
        self._logger = core_utilities.get_cls_logger(type(self))
        self._mutwo_parameter_dict_to_simple_event = (
            mutwo_parameter_dict_to_simple_event
        )
        self._midi_pitch_to_mutwo_pitch = midi_pitch_to_mutwo_pitch
        self._midi_velocity_to_mutwo_volume = midi_velocity_to_mutwo_volume

    # ###################################################################### #
    #                          static methods                                #
    # ###################################################################### #

    @staticmethod
    def _get_message_type_to_midi_message_list(
        midi_file_to_convert: mido.MidiFile,
    ) -> MessageTypeToMidiMessageList:
        message_type_to_midi_message_list = {}
        for midi_track in midi_file_to_convert.tracks:
            absolute_tick = 0
            for midi_message in midi_track:
                message_type = midi_message.type
                if message_type not in message_type_to_midi_message_list:
                    message_type_to_midi_message_list.update({message_type: []})
                absolute_tick += midi_message.time
                midi_message_with_absolute_tick = copy.deepcopy(midi_message)
                midi_message_with_absolute_tick.time = int(absolute_tick)
                message_type_to_midi_message_list[message_type].append(
                    midi_message_with_absolute_tick
                )
        for midi_message_list in message_type_to_midi_message_list.values():
            midi_message_list.sort(key=lambda midi_message: midi_message.time)
        return message_type_to_midi_message_list

    @staticmethod
    def _note_pair_tuple_to_start_and_stop_tuple_to_note_pair_list(
        note_pair_tuple: NotePairTuple,
    ) -> StartAndStopTupleToNotePairList:
        start_and_stop_tuple_to_note_pair_list = {}
        for note_pair in note_pair_tuple:
            start_and_stop_tuple = tuple(
                note_message.time for note_message in note_pair  # type: ignore
            )
            if start_and_stop_tuple not in start_and_stop_tuple_to_note_pair_list:
                start_and_stop_tuple_to_note_pair_list.update(
                    {start_and_stop_tuple: []}
                )
            start_and_stop_tuple_to_note_pair_list[start_and_stop_tuple].append(
                note_pair
            )
        return start_and_stop_tuple_to_note_pair_list

    @staticmethod
    def _add_simple_event_to_sequential_event(
        sequential_event: core_events.SequentialEvent,
        start: int,
        simple_event: core_events.SimpleEvent,
    ):
        difference = start - sequential_event.duration.duration
        if difference > 0:
            rest = core_events.SimpleEvent(difference)
            sequential_event.append(rest)
        sequential_event.append(simple_event)

    @staticmethod
    def _tick_to_duration(
        tick: int, ticks_per_beat: int
    ) -> core_parameters.DirectDuration:
        return core_parameters.DirectDuration(fractions.Fraction(tick, ticks_per_beat))

    # ###################################################################### #
    #                          private methods                               #
    # ###################################################################### #

    def _get_note_off_partner(
        self,
        note_on_message: mido.Message | mido.MetaMessage,
        note_off_message_list: list[mido.Message | mido.MetaMessage],
    ) -> typing.Optional[mido.Message]:
        def is_valid_note_off_message(
            note_off_message: mido.Message | mido.MetaMessage,
        ) -> bool:
            test_list = [
                note_off_message.time >= note_on_message.time,  # type: ignore
                note_on_message.note == note_off_message.note,  # type: ignore
                note_on_message.channel == note_off_message.channel,  # type: ignore
            ]
            return all(test_list)

        try:
            note_off_message = next(
                filter(is_valid_note_off_message, note_off_message_list)
            )
            assert isinstance(note_off_message, mido.Message)
        except StopIteration:
            self._logger.warning(
                "Invalid midi file: "
                "Found note on message without any suitable "
                "note off message partner. The note on message is: "
                f"'{note_on_message}'."
            )
            note_off_message = None

        return note_off_message

    def _get_note_pair_tuple(
        self,
        message_type_to_midi_message_list: MessageTypeToMidiMessageList,
    ) -> NotePairTuple:
        try:
            note_on_message_list = message_type_to_midi_message_list["note_on"]
        except KeyError:
            self._logger.debug("No 'note_on' messages were found!")
            return tuple([])

        try:
            note_off_message_list = copy.deepcopy(
                message_type_to_midi_message_list["note_off"]
            )
        except KeyError:
            self._logger.warning(
                "No 'note_off' messages were found! "
                "This is strange, because 'note_on' messages could be found. "
                "Maybe you have a midi file which doesn't use 'note_off'"
                "messages but only 'note_on' messages with velocity=0?"
                " This is currently not supported, see"
                " also https://github.com/mutwo-org/mutwo.midi/issues/4."
            )
            return tuple([])

        note_pair_list = []
        for note_on_message in note_on_message_list:
            note_off_message = self._get_note_off_partner(
                note_on_message, note_off_message_list
            )
            if note_off_message is not None:
                note_pair = (note_on_message, note_off_message)
                self._logger.debug(
                    f"Found note_pair (on: {note_on_message}, off: {note_off_message})"
                )
                note_pair_list.append(note_pair)
                del note_off_message_list[note_off_message_list.index(note_off_message)]

        note_pair_list.sort(key=lambda note_pair: note_pair[0].time)
        return tuple(note_pair_list)

    def _note_pair_list_to_simple_event(
        self, note_pair_list: list[NotePair], ticks_per_beat: int
    ) -> core_events.SimpleEvent:
        midi_pitch_list = []
        velocity_list = []
        for note_pair in note_pair_list:
            note_on, _ = note_pair
            # TODO(take pitch bend into account!)
            midi_pitch_list.append((note_on.note, 0))  # type: ignore
            velocity_list.append(note_on.velocity)  # type: ignore

        average_velocity = int(np.average(velocity_list))
        mutwo_volume = self._midi_velocity_to_mutwo_volume(average_velocity)

        mutwo_pitch_list = [
            self._midi_pitch_to_mutwo_pitch(midi_pitch)
            for midi_pitch in midi_pitch_list
        ]

        note_on, note_off = note_pair_list[0]
        tick = note_off.time - note_on.time  # type: ignore
        duration = MidiFileToEvent._tick_to_duration(tick, ticks_per_beat)

        # Use default values defined in configurations modules to ensure
        # stability in case user changes the values.
        mutwo_parameter_dict = {
            core_converters.configurations.DEFAULT_DURATION_TO_SEARCH_NAME: duration,
            music_converters.configurations.DEFAULT_PITCH_LIST_TO_SEARCH_NAME: mutwo_pitch_list,
            music_converters.configurations.DEFAULT_VOLUME_TO_SEARCH_NAME: mutwo_volume,
        }
        simple_event = self._mutwo_parameter_dict_to_simple_event(mutwo_parameter_dict)
        self._logger.debug(
            f"Midi data -> Mutwo data -> SimpleEvent:\n\t"
            f"Midi data: (tick={tick},velocity_list={velocity_list},midi_pitch_list={midi_pitch_list})\n\t"
            f"Mutwo data: {mutwo_parameter_dict}\n\t"
            f"SimpleEvent: {simple_event}"
        )
        return simple_event

    def _note_pair_tuple_to_simultaneous_event(
        self, note_pair_tuple: NotePairTuple, ticks_per_beat: int
    ) -> core_events.SimultaneousEvent[
        core_events.SequentialEvent[core_events.SimpleEvent]
    ]:
        simultaneous_event = core_events.SimultaneousEvent([])

        start_and_stop_tuple_to_note_pair_list = (
            MidiFileToEvent._note_pair_tuple_to_start_and_stop_tuple_to_note_pair_list(
                note_pair_tuple
            )
        )
        for start_and_stop_tuple in sorted(
            start_and_stop_tuple_to_note_pair_list.keys(),
            key=lambda start_and_stop_tuple: start_and_stop_tuple[0],
        ):
            start_tick, _ = start_and_stop_tuple
            start = self._tick_to_duration(start_tick, ticks_per_beat)
            note_pair_list = start_and_stop_tuple_to_note_pair_list[
                start_and_stop_tuple
            ]
            simple_event = self._note_pair_list_to_simple_event(
                note_pair_list, ticks_per_beat
            )
            is_added = False
            for sequential_event in simultaneous_event:
                duration = sequential_event.duration
                difference = start - duration
                if difference >= 0:
                    self._add_simple_event_to_sequential_event(
                        sequential_event, start, simple_event
                    )
                    is_added = True
                    break
            if not is_added:
                simultaneous_event.append(core_events.SequentialEvent([]))
                self._add_simple_event_to_sequential_event(
                    simultaneous_event[-1], start, simple_event
                )

        return simultaneous_event

    def _note_pair_tuple_and_set_tempo_message_list_to_simultaneous_event(
        self,
        note_pair_tuple: NotePairTuple,
        set_tempo_message_list: list[mido.Message | mido.MetaMessage],
        ticks_per_beat: int,
    ) -> core_events.SimultaneousEvent[
        core_events.SequentialEvent[core_events.SimpleEvent]
    ]:
        simultaneous_event = self._note_pair_tuple_to_simultaneous_event(
            note_pair_tuple, ticks_per_beat
        )
        # TODO(apply tempo messages)
        return simultaneous_event

    def _midi_file_to_mutwo_event(
        self, midi_file_to_convert: mido.MidiFile
    ) -> core_events.abc.Event:
        ticks_per_beat = midi_file_to_convert.ticks_per_beat
        message_type_to_midi_message_list = (
            MidiFileToEvent._get_message_type_to_midi_message_list(midi_file_to_convert)
        )
        note_pair_tuple = self._get_note_pair_tuple(message_type_to_midi_message_list)
        try:
            set_tempo_message_list = message_type_to_midi_message_list["set_tempo"]
        except KeyError:
            set_tempo_message_list = []
        return self._note_pair_tuple_and_set_tempo_message_list_to_simultaneous_event(
            note_pair_tuple, set_tempo_message_list, ticks_per_beat
        )

    # ###################################################################### #
    #                          public methods                                #
    # ###################################################################### #

    def convert(
        self, midi_file_path_or_mido_midi_file: str | mido.MidiFile
    ) -> core_events.abc.Event:
        """Convert midi file to mutwo event.

        :param midi_file_path_or_mido_midi_file: The midi file which shall
            be converted. Can either be a file path or a :class:`MidiFile`
            object from the `mido <https://github.com/mido/mido>`_ package.
        :type midi_file_path_or_mido_midi_file: str | mido.MidiFile
        """

        if isinstance(midi_file_path_or_mido_midi_file, str):
            midi_file = mido.MidiFile(midi_file_path_or_mido_midi_file)
        elif isinstance(midi_file_path_or_mido_midi_file, mido.MidiFile):
            midi_file = midi_file_path_or_mido_midi_file
        else:
            raise TypeError(
                (
                    f"Found '{midi_file_path_or_mido_midi_file}' of"
                    "unsupported type"
                    f"'{type(midi_file_path_or_mido_midi_file)}' for"
                    "parameter 'midi_file_path_or_mido_midi_file'! "
                    "Please enter either a file name (str) or a MidiFile"
                    " object (from the mido package)."
                )
            )
        return self._midi_file_to_mutwo_event(midi_file)
