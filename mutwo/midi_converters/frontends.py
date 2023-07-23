"""Render midi files (SMF) from mutwo data.

"""

import functools
import itertools
import operator
import typing

import mido  # type: ignore

from mutwo import core_constants
from mutwo import core_converters
from mutwo import core_events
from mutwo import core_parameters
from mutwo import core_utilities
from mutwo import midi_converters
from mutwo import music_converters
from mutwo import music_parameters

__all__ = (
    "SimpleEventToControlMessageTuple",
    "CentDeviationToPitchBendingNumber",
    "MutwoPitchToMidiPitch",
    "EventToMidiFile",
)

ConvertableEvent = (
    core_events.SimpleEvent
    | core_events.SequentialEvent[core_events.SimpleEvent]
    | core_events.SimultaneousEvent[
        core_events.SequentialEvent[core_events.SimpleEvent]
    ]
)


class SimpleEventToControlMessageTuple(core_converters.SimpleEventToAttribute):
    """Convert :class:`mutwo.core_events.SimpleEvent` to a tuple of control messages"""

    def __init__(
        self,
        attribute_name: typing.Optional[str] = None,
        exception_value: tuple[mido.Message, ...] = tuple([]),
    ):
        super().__init__(
            attribute_name
            or midi_converters.configurations.DEFAULT_CONTROL_MESSAGE_TUPLE_ATTRIBUTE_NAME,
            exception_value,
        )


class CentDeviationToPitchBendingNumber(core_converters.abc.Converter):
    """Convert cent deviation to midi pitch bend number.

    :param maximum_pitch_bend_deviation: sets the maximum pitch bending range in cents.
        This value depends on the particular used software synthesizer and its settings,
        because it is up to the respective synthesizer how to interpret the pitch
        bending messages. By default mutwo sets the value to 200 cents which
        seems to be the most common interpretation among different manufacturers.
    :type maximum_pitch_bend_deviation: int
    """

    def __init__(self, maximum_pitch_bend_deviation: typing.Optional[float] = None):
        self._logger = core_utilities.get_cls_logger(type(self))
        self._maximum_pitch_bend_deviation = maximum_pitch_bend_deviation = (
            maximum_pitch_bend_deviation
            or midi_converters.configurations.DEFAULT_MAXIMUM_PITCH_BEND_DEVIATION_IN_CENTS
        )
        self._pitch_bending_warning = (
            f"Maximum pitch bending is {maximum_pitch_bend_deviation} cents up or down!"
        )

    def _warn_pitch_bending(self, cent_deviation: core_constants.Real):
        self._logger.warning(
            f"Maximum pitch bending is {self._maximum_pitch_bend_deviation} "
            "cents up or down! Found prohibited necessity for pitch "
            f"bending with cent_deviation = {cent_deviation}. "
            "Mutwo normalized pitch bending to the allowed border."
            " Increase the 'maximum_pitch_bend_deviation' argument in the "
            "CentDeviationToPitchBendingNumber instance."
        )

    def convert(
        self,
        cent_deviation: core_constants.Real,
    ) -> int:
        if cent_deviation >= self._maximum_pitch_bend_deviation:
            self._warn_pitch_bending(cent_deviation)
            cent_deviation = self._maximum_pitch_bend_deviation
        elif cent_deviation <= -self._maximum_pitch_bend_deviation:
            self._warn_pitch_bending(cent_deviation)
            cent_deviation = -self._maximum_pitch_bend_deviation

        return round(
            core_utilities.scale(
                cent_deviation,
                -self._maximum_pitch_bend_deviation,
                self._maximum_pitch_bend_deviation,
                -midi_converters.constants.NEUTRAL_PITCH_BEND,
                midi_converters.constants.NEUTRAL_PITCH_BEND,
            )
        )


class MutwoPitchToMidiPitch(core_converters.abc.Converter):
    """Convert mutwo pitch to midi pitch number and midi pitch bend number.

    :param maximum_pitch_bend_deviation: sets the maximum pitch bending range in cents.
        This value depends on the particular used software synthesizer and its settings,
        because it is up to the respective synthesizer how to interpret the pitch
        bending messages. By default mutwo sets the value to 200 cents which
        seems to be the most common interpretation among different manufacturers.
    :type maximum_pitch_bend_deviation: int
    """

    def __init__(
        self,
        cent_deviation_to_pitch_bending_number: CentDeviationToPitchBendingNumber = CentDeviationToPitchBendingNumber(),
    ):
        self._cent_deviation_to_pitch_bending_number = (
            cent_deviation_to_pitch_bending_number
        )

    def convert(
        self,
        mutwo_pitch_to_convert: music_parameters.abc.Pitch,
        midi_note: typing.Optional[int] = None,
    ) -> midi_converters.constants.MidiPitch:
        """Find midi note and pitch bending for given mutwo pitch

        :param mutwo_pitch_to_convert: The mutwo pitch which shall be converted.
        :type mutwo_pitch_to_convert: music_parameters.abc.Pitch
        :param midi_note: Can be set to a midi note value if one wants to force
            the converter to calculate the pitch bending deviation for the passed
            midi note. If this argument is ``None`` the converter will simply use
            the closest midi pitch number to the passed mutwo pitch. Default to ``None``.
        :type midi_note: typing.Optional[int]
        """
        f = mutwo_pitch_to_convert.frequency
        if midi_note:
            closest_midi_pitch = midi_note
        else:
            closest_midi_pitch = core_utilities.find_closest_index(
                f, music_parameters.constants.MIDI_PITCH_FREQUENCY_TUPLE
            )
        Δcents_to_closest_midi_pitch = music_parameters.abc.Pitch.hertz_to_cents(
            music_parameters.constants.MIDI_PITCH_FREQUENCY_TUPLE[closest_midi_pitch],
            f,
        )
        pb = self._cent_deviation_to_pitch_bending_number.convert(
            Δcents_to_closest_midi_pitch
        )
        return closest_midi_pitch, pb


class EventToMidiFile(core_converters.abc.Converter):
    """Class for rendering standard midi files (SMF) from mutwo data.

    Mutwo offers a wide range of options how the respective midi file shall
    be rendered and how mutwo data shall be translated. This is necessary due
    to the limited and not always unambiguous nature of musical encodings in
    midi files. In this way the user can tweak the conversion routine to her
    or his individual needs.

    :param simple_event_to_pitch_list: Function to extract from a
        :class:`mutwo.core_events.SimpleEvent` a tuple that contains pitch objects
        (objects that inherit from :class:`mutwo.music_parameters.abc.Pitch`).
        By default it asks the Event for its :attr:`pitch_list` attribute
        (because by default :class:`mutwo.music_events.NoteLike` objects are expected).
        When using different Event classes than ``NoteLike`` with a different name for
        their pitch property, this argument should be overridden. If the function call
        raises an :obj:`AttributeError` (e.g. if no pitch can be extracted),
        mutwo will interpret the event as a rest.
    :type simple_event_to_pitch_list: typing.Callable[
            [core_events.SimpleEvent], tuple[music_parameters.abc.Pitch, ...]]
    :param simple_event_to_volume: Function to extract the volume from a
        :class:`mutwo.core_events.SimpleEvent` in the purpose of generating midi notes.
        The function should return an object that inhertis from
        :class:`mutwo.music_parameters.abc.Volume`. By default it asks the Event for
        its :attr:`volume` attribute (because by default
        :class:`mutwo.music_events.NoteLike` objects are expected).
        When using different Event classes than ``NoteLike`` with a
        different name for their volume property, this argument should be overridden.
        If the function call raises an :obj:`AttributeError` (e.g. if no volume can be
        extracted), mutwo will interpret the event as a rest.
    :type simple_event_to_volume: typing.Callable[
            [core_events.SimpleEvent], music_parameters.abc.Volume]
    :param simple_event_to_control_message_tuple: Function to generate midi control messages
        from a simple event. By default no control messages are generated. If the
        function call raises an AttributeError (e.g. if an expected control value isn't
        available) mutwo will interpret the event as a rest.
    :type simple_event_to_control_message_tuple: typing.Callable[
            [core_events.SimpleEvent], tuple[mido.Message, ...]]
    :param midi_file_type: Can either be 0 (for one-track midi files) or 1 (for
         synchronous multi-track midi files). Mutwo doesn't offer support for generating
         type 2 midi files (midi files with asynchronous tracks).
    :type midi_file_type: int
    :param available_midi_channel_tuple: tuple containing integer where each integer
        represents the number of the used midi channel. Integer can range from 0 to 15.
        Higher numbers of available_midi_channel_tuple (like all 16) are recommended when
        rendering microtonal music. It shall be remarked that midi-channel 9 (or midi
        channel 10 when starting to count from 1) is often ignored by several software
        synthesizer, because this channel is reserved for percussion instruments.
    :type available_midi_channel_tuple: tuple[int, ...]
    :param distribute_midi_channels: This parameter is only relevant if more than one
        :class:`~mutwo.core_events.SequentialEvent` is passed to the convert method.
        If set to ``True`` each :class:`~mutwo.core_events.SequentialEvent`
        only makes use of exactly n_midi_channel (see next parameter).
        If set to ``False`` each converted :class:`SequentialEvent` is allowed to make use of all
        available channels. If set to ``True`` and the amount of necessary MidiTracks is
        higher than the amount of available channels, mutwo will silently cycle through
        the list of available midi channel.
    :type distribute_midi_channels: bool
    :param midi_channel_count_per_track: This parameter is only relevant for
        distribute_midi_channels == True. It sets how many midi channels are assigned
        to one SequentialEvent. If microtonal chords shall be played by
        one SequentialEvent (via pitch bending messages) a higher number than 1 is
        recommended. Defaults to 1.
    :type midi_channel_count_per_track: int
    :param mutwo_pitch_to_midi_pitch: class to convert from mutwo pitches
        to midi pitches. Default to :class:`MutwoPitchToMidiPitch`.
    :type mutwo_pitch_to_midi_pitch: :class:`MutwoPitchToMidiPitch`
    :param ticks_per_beat: Sets the timing precision of the midi file. From the mido
        documentation: "Typical values range from 96 to 480 but some use even more
        ticks per beat".
    :type ticks_per_beat: int
    :param instrument_name: Sets the midi instrument of all channels.
    :type instrument_name: str
    :param tempo_envelope: All Midi files should specify their tempo. The default
        value of mutwo is 120 BPM (this is also the value that is assumed by any
        midi-file-reading-software if no tempo has been specified). Tempo changes
        are supported (and will be written to the resulting midi file).
    :type tempo_envelope: core_events.TempoEnvelope

    **Example**:

    >>> from mutwo import midi_converters
    >>> from mutwo import music_parameters
    >>> # midi file converter that assign a middle c to all events
    >>> midi_converter = midi_converters.EventToMidiFile(
    ...     simple_event_to_pitch_list=lambda event: (music_parameters.WesternPitch('c'),)
    ... )

    **Disclaimer**:
        The current implementation doesn't support time-signatures (the written time
        signature is always 4/4 for now).
    """

    _tempo_point_converter = core_converters.TempoPointToBeatLengthInSeconds()

    def __init__(
        self,
        simple_event_to_pitch_list: typing.Callable[
            [core_events.SimpleEvent], tuple[music_parameters.abc.Pitch, ...]
        ] = music_converters.SimpleEventToPitchList(),  # type: ignore
        simple_event_to_volume: typing.Callable[
            [core_events.SimpleEvent], music_parameters.abc.Volume
        ] = music_converters.SimpleEventToVolume(),  # type: ignore
        simple_event_to_control_message_tuple: typing.Callable[
            [core_events.SimpleEvent], tuple[mido.Message, ...]
        ] = SimpleEventToControlMessageTuple(),
        midi_file_type: int = None,
        available_midi_channel_tuple: tuple[int, ...] = None,
        distribute_midi_channels: bool = False,
        midi_channel_count_per_track: typing.Optional[int] = None,
        mutwo_pitch_to_midi_pitch: MutwoPitchToMidiPitch = MutwoPitchToMidiPitch(),
        ticks_per_beat: typing.Optional[int] = None,
        instrument_name: typing.Optional[str] = None,
        tempo_envelope: typing.Optional[core_events.TempoEnvelope] = None,
    ):
        self._logger = core_utilities.get_cls_logger(type(self))
        self._midi_file_type = (
            midi_file_type or midi_converters.configurations.DEFAULT_MIDI_FILE_TYPE
        )
        self._available_midi_channel_tuple = (
            available_midi_channel_tuple
            or midi_converters.configurations.DEFAULT_AVAILABLE_MIDI_CHANNEL_TUPLE
        )
        self._midi_channel_count_per_track = (
            midi_channel_count_per_track
            or midi_converters.configurations.DEFAULT_MIDI_CHANNEL_COUNT_PER_TRACK
        )
        self._ticks_per_beat = (
            ticks_per_beat or midi_converters.configurations.DEFAULT_TICKS_PER_BEAT
        )
        self._instrument_name = (
            instrument_name
            or midi_converters.configurations.DEFAULT_MIDI_INSTRUMENT_NAME
        )
        self._tempo_envelope = (
            tempo_envelope or midi_converters.configurations.DEFAULT_TEMPO_ENVELOPE
        )
        self._simple_event_to_pitch_list = simple_event_to_pitch_list
        self._simple_event_to_volume = simple_event_to_volume
        self._simple_event_to_control_message_tuple = (
            simple_event_to_control_message_tuple
        )
        self._distribute_midi_channels = distribute_midi_channels
        self._mutwo_pitch_to_midi_pitch = mutwo_pitch_to_midi_pitch
        self._assert_midi_file_type_has_correct_value(self._midi_file_type)
        self._assert_available_midi_channel_tuple_has_correct_value(
            self._available_midi_channel_tuple
        )

    # ###################################################################### #
    #                          static methods                                #
    # ###################################################################### #

    @staticmethod
    def _assert_midi_file_type_has_correct_value(midi_file_type: int):
        try:
            assert midi_file_type in (0, 1)
        except AssertionError:
            raise ValueError(
                f"Unknown midi_file_type '{midi_file_type}'. "
                "Only midi type 0 and 1 are supported."
            )

    @staticmethod
    def _assert_available_midi_channel_tuple_has_correct_value(
        available_midi_channel_tuple: tuple[int, ...],
    ):
        # check for correct range of each number
        for mc in available_midi_channel_tuple:
            if not (mc in midi_converters.constants.ALLOWED_MIDI_CHANNEL_TUPLE):
                raise ValueError(
                    f"Found unknown midi channel '{mc}' "
                    "in available_midi_channel_tuple."
                    " Only midi channel "
                    f"'{midi_converters.constants.ALLOWED_MIDI_CHANNEL_TUPLE}' "
                    "are allowed."
                )

        # check for duplicate
        if len(available_midi_channel_tuple) != len(set(available_midi_channel_tuple)):
            raise ValueError(
                "Found duplicate in available_midi_channel_tuple "
                f"'{available_midi_channel_tuple}'."
            )

    # ###################################################################### #
    #                         helper methods                                 #
    # ###################################################################### #

    def _adjust_beat_length_in_microseconds(
        self,
        tempo_point: core_constants.Real | core_parameters.DirectTempoPoint,
        beat_length_in_microseconds: int,
    ) -> int:
        """This method makes sure that ``beat_length_in_microseconds`` isn't too big.

        Standard midi files define a slowest allowed tempo which is around 3.5 BPM.
        In case the tempo is lower than this slowest allowed tempo, `mutwo` will
        automatically set the tempo to the lowest allowed tempo.
        """
        bl = beat_length_in_microseconds
        if bl >= midi_converters.constants.MAXIMUM_MICROSECONDS_PER_BEAT:
            bl = midi_converters.constants.MAXIMUM_MICROSECONDS_PER_BEAT
            bpm = mido.tempo2bpm(
                midi_converters.constants.MAXIMUM_MICROSECONDS_PER_BEAT
            )
            self._logger.warning(
                f"TempoPoint '{tempo_point}' is too slow for "
                "Standard Midi Files. "
                f"The slowest possible tempo is '{bpm}' BPM."
                "Tempo has been set to"
                f" '{bpm}' BPM.",
            )
        return bl

    def _beats_per_minute_to_beat_length_in_microseconds(
        self, beats_per_minute: core_constants.Real
    ) -> int:
        """Method for converting beats per minute (BPM) to midi tempo.
        Midi tempo is stated in beat length in microseconds.
        """
        bl_in_seconds = self._tempo_point_converter.convert(beats_per_minute)
        return int(bl_in_seconds * midi_converters.constants.MIDI_TEMPO_FACTOR)

    def _find_available_midi_channel_tuple_per_sequential_event(
        self,
        simultaneous_event: core_events.SimultaneousEvent[
            core_events.SequentialEvent[core_events.SimpleEvent]
        ],
    ) -> tuple[tuple[int, ...], ...]:
        """Find midi channels for each SequentialEvent.

        Depending on whether distribute_midi_channels has been set
        to True this method distributes all available midi channels
        on the respective SequentialEvents.
        """
        if self._distribute_midi_channels:
            mchannel_cycle = itertools.cycle(self._available_midi_channel_tuple)
            return tuple(
                tuple(
                    next(mchannel_cycle)
                    for _ in range(self._midi_channel_count_per_track)
                )
                for _ in simultaneous_event
            )
        else:
            return tuple(self._available_midi_channel_tuple for _ in simultaneous_event)

    def _beats_to_ticks(
        self, absolute_time: core_parameters.abc.Duration | typing.Any
    ) -> int:
        abs_t = core_events.configurations.UNKNOWN_OBJECT_TO_DURATION(absolute_time)
        return int(self._ticks_per_beat * abs_t.duration)

    # ###################################################################### #
    #             methods for converting mutwo data to midi data             #
    # ###################################################################### #

    def _tempo_envelope_to_midi_message_tuple(
        self, tempo_envelope: core_events.TempoEnvelope
    ) -> tuple[mido.MetaMessage, ...]:
        """Converts a SequentialEvent of ``EnvelopeEvent`` to midi Tempo messages."""

        offset_iterator = core_utilities.accumulate_from_n(
            tempo_envelope.get_parameter("duration"), core_parameters.DirectDuration(0)
        )

        mlist = []
        for abs_t, tempo_point in zip(offset_iterator, tempo_envelope.value_tuple):
            absolute_tick = self._beats_to_ticks(abs_t)
            bl = self._beats_per_minute_to_beat_length_in_microseconds(tempo_point)
            bl = self._adjust_beat_length_in_microseconds(tempo_point, bl)
            tempom = mido.MetaMessage("set_tempo", tempo=bl, time=absolute_tick)
            mlist.append(tempom)

        return tuple(mlist)

    def _tune_pitch(
        self,
        absolute_tick_start: int,
        absolute_tick_end: int,
        pitch_to_tune: music_parameters.abc.Pitch,
        midi_channel: int,
    ) -> tuple[midi_converters.constants.MidiNote, tuple[mido.Message, ...]]:
        tick_count = absolute_tick_end - absolute_tick_start
        # We replace the original pitch object with a pitch object that doesn't
        # start any complex computations when asking for its 'frequency' attribute.
        pitch_to_tune = music_parameters.DirectPitch(
            pitch_to_tune.frequency, envelope=pitch_to_tune.envelope
        )
        # We have to use one tick less, so that at
        # "pitch_envelope.value_at(tick_count)" we already reached the
        # end of the envelope.
        penvelope = pitch_to_tune.resolve_envelope(tick_count - 1)
        # We will convert the pitch envelope to numerical values for better performance
        numerical_penvelope = core_events.Envelope(
            [
                [absolute_time, value, event.curve_shape]
                for absolute_time, value, event in zip(
                    penvelope.absolute_time_tuple,
                    penvelope.value_tuple,
                    penvelope,
                )
            ]
        )
        end = 1 if not penvelope.duration else None
        avg_cent = numerical_penvelope.get_average_parameter(end=end)
        avg_p = penvelope.value_to_parameter(avg_cent)
        midi_pitch, pb = self._mutwo_pitch_to_midi_pitch.convert(avg_p)
        first_pitch_bending_message_time = absolute_tick_start
        if absolute_tick_start != 0:
            # if possible add bending one tick earlier to avoid glitches
            first_pitch_bending_message_time -= 1

        pbm_list = []  # pitch bending messages
        if numerical_penvelope.is_static:
            pbm_list.append(
                mido.Message(
                    "pitchwheel",
                    channel=midi_channel,
                    pitch=pb,
                    time=first_pitch_bending_message_time,
                )
            )
        else:
            avg_p_f = avg_p.frequency
            for t in range(0, tick_count):
                abstract_cents = numerical_penvelope.parameter_at(t)
                f = penvelope.value_to_parameter(abstract_cents).frequency
                pb = self._mutwo_pitch_to_midi_pitch._cent_deviation_to_pitch_bending_number.convert(
                    music_parameters.abc.Pitch.hertz_to_cents(avg_p_f, f)
                )
                pitch_bending_message = mido.Message(
                    "pitchwheel",
                    channel=midi_channel,
                    pitch=pb,
                    time=t + absolute_tick_start,
                )
                pbm_list.append(pitch_bending_message)
        return midi_pitch, tuple(pbm_list)

    def _note_information_to_midi_message_tuple(
        self,
        absolute_tick_start: int,
        absolute_tick_end: int,
        velocity: int,
        pitch: music_parameters.abc.Pitch,
        midi_channel: int,
    ) -> tuple[mido.Message, ...]:
        """Generate 'pitch bending', 'note on' and 'note off' messages for one tone."""
        p, pitch_bending_message_tuple = self._tune_pitch(
            absolute_tick_start,
            absolute_tick_end,
            pitch,
            midi_channel,
        )

        midi_message_list = list(pitch_bending_message_tuple)

        for t, m in (
            (absolute_tick_start, "note_on"),
            (absolute_tick_end, "note_off"),
        ):
            midi_message_list.append(
                mido.Message(m, note=p, velocity=velocity, time=t, channel=midi_channel)
            )

        return tuple(midi_message_list)

    def _extracted_data_to_midi_message_tuple(
        self,
        absolute_time: core_parameters.abc.Duration,
        duration: core_constants.DurationType,
        available_midi_channel_tuple_cycle: typing.Iterator,
        pitch_list: tuple[music_parameters.abc.Pitch, ...],
        volume: music_parameters.abc.Volume,
        control_message_tuple: tuple[mido.Message, ...],
    ) -> tuple[mido.Message, ...]:
        """Generates pitch-bend / note-on / note-off messages for each tone in a chord.

        Concatenates the midi messages for every played tone with the global control
        messages.

        Gets as an input relevant data for midi message generation that has been
        extracted from a :class:`mutwo.core_events.abc.Event` object.
        """
        abs_tick_start = self._beats_to_ticks(absolute_time)
        abs_tick_end = abs_tick_start + self._beats_to_ticks(duration)
        velocity = volume.midi_velocity

        mlist = []

        # add control messages
        for cm in control_message_tuple:
            cm.time = abs_tick_start
            mlist.append(cm)

        # add note related messages
        for p in pitch_list:
            mlist.extend(
                self._note_information_to_midi_message_tuple(
                    abs_tick_start,
                    abs_tick_end,
                    velocity,
                    p,
                    next(available_midi_channel_tuple_cycle),
                )
            )

        return tuple(mlist)

    def _simple_event_to_midi_message_tuple(
        self,
        simple_event: core_events.SimpleEvent,
        absolute_time: core_parameters.abc.Duration,
        available_midi_channel_tuple_cycle: typing.Iterator,
    ) -> tuple[mido.Message, ...]:
        """Converts ``SimpleEvent`` (or any object that inherits from ``SimpleEvent``).

        Return tuple filled with midi messages that represent the mutwo data in the
        midi format.

        The timing here is absolute. Only later at the
        `_midi_message_tuple_to_midi_track` method the timing
        becomes relative
        """

        extracted_data_list = []

        # try to extract the relevant data
        is_rest = False
        for p, extraction_function in (
            ("pitch_list", self._simple_event_to_pitch_list),
            ("volume", self._simple_event_to_volume),
            ("control_message_tuple", self._simple_event_to_control_message_tuple),
        ):
            try:
                d = extraction_function(simple_event)
            except AttributeError:
                is_rest = True
            else:
                if d is None:
                    self._logger.warning(
                        "Extracting '{p}' from event '{simple_event}' "
                        "returned 'None'! Converter autoset this event to "
                        "a rest."
                    )
                    is_rest = True
            if is_rest:
                break
            extracted_data_list.append(d)

        # if not all relevant data could be extracted, simply ignore the
        # event
        if is_rest:
            return tuple([])

        # otherwise generate midi messages from the extracted data
        return self._extracted_data_to_midi_message_tuple(
            absolute_time,
            simple_event.duration,
            available_midi_channel_tuple_cycle,
            *extracted_data_list,  # type: ignore
        )

    def _sequential_event_to_midi_message_tuple(
        self,
        sequential_event: core_events.SequentialEvent[
            core_events.SimpleEvent | core_events.SequentialEvent
        ],
        available_midi_channel_tuple: tuple[int, ...],
        absolute_time: core_parameters.abc.Duration = core_parameters.DirectDuration(0),
    ) -> tuple[mido.Message, ...]:
        """Iterates through the ``SequentialEvent`` and converts each ``SimpleEvent``.

        Return unsorted tuple of Midi messages where the time attribute of each message
        is the absolute time in ticks.
        """

        mlist: list[mido.Message] = []
        mchannel_cycle = itertools.cycle(available_midi_channel_tuple)

        # fill midi track with the content of the sequential event
        for local_abs_time, sim_or_seq in zip(
            sequential_event.absolute_time_tuple, sequential_event
        ):
            global_abs_time = local_abs_time + absolute_time
            if isinstance(sim_or_seq, core_events.SimpleEvent):
                mtuple = self._simple_event_to_midi_message_tuple(
                    sim_or_seq, global_abs_time, mchannel_cycle
                )
                self._logger.debug(
                    f"SimpleEvent -> MidiMessageData:\n\t{sim_or_seq} -> {mtuple}"
                )
            else:
                mtuple = self._sequential_event_to_midi_message_tuple(
                    sim_or_seq,
                    available_midi_channel_tuple,
                    global_abs_time,
                )
            mlist.extend(mtuple)

        return tuple(mlist)

    def _midi_message_tuple_to_midi_track(
        self,
        midi_message_tuple: tuple[mido.Message | mido.MetaMessage, ...],
        duration: core_constants.DurationType,
        is_first_track: bool = False,
    ) -> mido.MidiTrack:
        """Convert unsorted midi message with absolute timing to a midi track.

        In the resulting midi track the timing of the messages is relative.
        """
        self._logger.debug(
            "Convert midi messages -> MidiTrack\n\t" f"msg-tuple: {midi_message_tuple}"
        )

        track = mido.MidiTrack([])
        track.append(mido.MetaMessage("instrument_name", name=self._instrument_name))

        if is_first_track:
            # standard time signature 4/4
            track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4))
            midi_message_tuple += self._tempo_envelope_to_midi_message_tuple(
                self._tempo_envelope
            )

        # If event is empty and it isn't the first track
        # (e.g. no tempo envelope was added)
        if not midi_message_tuple:
            return track

        sorted_m = sorted(midi_message_tuple, key=lambda message: message.time)
        sorted_m.append(
            mido.MetaMessage(
                "end_of_track",
                time=max((sorted_m[-1].time, self._beats_to_ticks(duration))),
            )
        )

        # absolute time => relative time
        Δticks = tuple(m1.time - m0.time for m0, m1 in zip(sorted_m, sorted_m[1:]))
        Δticks = (sorted_m[0].time,) + Δticks
        for Δt, message in zip(Δticks, sorted_m):
            message.time = Δt

        track.extend(sorted_m)
        return track

    # ###################################################################### #
    #           methods for filling the midi file (only called once)         #
    # ###################################################################### #

    def _add_simple_event_to_midi_file(
        self, simple_event: core_events.SimpleEvent, midi_file: mido.MidiFile
    ) -> None:
        self._add_sequential_event_to_midi_file(
            core_events.SequentialEvent([simple_event]), midi_file
        )

    def _add_sequential_event_to_midi_file(
        self,
        sequential_event: core_events.SequentialEvent[core_events.SimpleEvent],
        midi_file: mido.MidiFile,
    ) -> None:
        self._add_simultaneous_event_to_midi_file(
            core_events.SimultaneousEvent([sequential_event]), midi_file
        )

    def _add_simultaneous_event_to_midi_file(
        self,
        simultaneous_event: core_events.SimultaneousEvent[
            core_events.SequentialEvent[core_events.SimpleEvent]
        ],
        midi_file: mido.MidiFile,
    ) -> None:
        # Depending on the midi_file_type either adds a tuple of MidiTrack
        # objects (for midi_file_type = 1) or adds only one MidiTrack
        # (for midi_file_type = 0).
        midi_channel_data = (
            self._find_available_midi_channel_tuple_per_sequential_event(
                simultaneous_event
            )
        )
        midi_data_per_seq_tuple = tuple(
            self._sequential_event_to_midi_message_tuple(seq, m)
            for seq, m in zip(simultaneous_event, midi_channel_data)
        )
        duration = simultaneous_event.duration

        # midi file type 0 -> only one track
        if self._midi_file_type == 0:
            midi_data_for_one_track = functools.reduce(
                operator.add, midi_data_per_seq_tuple
            )
            midi_track = self._midi_message_tuple_to_midi_track(
                midi_data_for_one_track, duration, is_first_track=True
            )
            midi_file.tracks.append(midi_track)

        # midi file type 1
        else:
            midi_track_iterator = (
                self._midi_message_tuple_to_midi_track(
                    m, duration, is_first_track=i == 0
                )
                for i, m in enumerate(midi_data_per_seq_tuple)
            )
            midi_file.tracks.extend(midi_track_iterator)

    def _event_to_midi_file(self, event_to_convert: ConvertableEvent) -> mido.MidiFile:
        """Convert mutwo event object to mido `MidiFile` object."""

        midi_file = mido.MidiFile(
            ticks_per_beat=self._ticks_per_beat, type=self._midi_file_type
        )

        # depending on the event types timing structure different methods are called
        match event_to_convert:
            case core_events.SimultaneousEvent():
                self._logger.debug("SimultaneousEvent -> MidiFile")
                self._add_simultaneous_event_to_midi_file(event_to_convert, midi_file)
            case core_events.SequentialEvent():
                self._logger.debug("SequentialEvent -> MidiFile")
                self._add_sequential_event_to_midi_file(event_to_convert, midi_file)
            case core_events.SimpleEvent():
                self._logger.debug("SimpleEvent -> MidiFile")
                self._add_simple_event_to_midi_file(event_to_convert, midi_file)
            case _:
                raise TypeError(
                    f"Can't convert object '{event_to_convert}' "
                    f"of type '{type(event_to_convert)}' to a MidiFile. "
                    "Supported types include all inherited classes "
                    f"from '{ConvertableEvent}'."
                )

        return midi_file

    # ###################################################################### #
    #               public methods for interaction with the user             #
    # ###################################################################### #

    def convert(
        self, event_to_convert: ConvertableEvent, path: typing.Optional[str] = None
    ) -> mido.MidiFile:
        """Render a Midi file to the converters path attribute from the given event.

        :param event_to_convert: The given event that shall be translated
            to a Midi file.
        :type event_to_convert: core_events.SimpleEvent | core_events.SequentialEvent[core_events.SimpleEvent] | core_events.SimultaneousEvent[core_events.SequentialEvent[core_events.SimpleEvent]]
        :param path: If this is a string the method will write a midi
            file to the given path. The typical file type extension '.mid'
            is recommended, but not mandatory. If set to `None` the
            method won't write a midi file to the disk, but it will simply
            return a :class:`mido.MidiFile` object. Default to `None`.
        :type path: typing.Optional[str]

        The following example generates a midi file that contains a simple ascending
        pentatonic scale:

        >>> from mutwo import core_events
        >>> from mutwo import music_events
        >>> from mutwo import music_parameters
        >>> from mutwo import midi_converters
        >>> ascending_scale = core_events.SequentialEvent(
        ...     [
        ...         music_events.NoteLike(music_parameters.WesternPitch(pitch), duration=1, volume=0.5)
        ...         for pitch in 'c d e g a'.split(' ')
        ...     ]
        ... )
        >>> midi_converter = midi_converters.EventToMidiFile(
        ...     available_midi_channel_tuple=(0,)
        ... )
        >>> # '.convert' creates a file, but also returns the
        >>> # respective 'mido.MidiFile' object
        >>> midifile = midi_converter.convert(ascending_scale, 'ascending_scale.mid')

        **Disclaimer:** when passing nested structures, make sure that the
        nested object matches the expected type. Unlike other mutwo
        converter classes (like :class:`mutwo.core_converters.TempoConverter`)
        :class:`EventToMidiFile` can't convert infinitely nested structures
        (due to the particular way how Midi files are defined). The deepest potential
        structure is a :class:`mutwo.core_events.SimultaneousEvent` (representing
        the complete MidiFile) that contains :class:`mutwo.core_events.SequentialEvent`
        (where each ``SequentialEvent`` represents one MidiTrack) that contains
        :class:`mutwo.core_events.SimpleEvent` (where each ``SimpleEvent``
        represents one midi note). If only one ``SequentialEvent`` is send,
        this ``SequentialEvent`` will be read as one MidiTrack in a MidiFile.
        If only one ``SimpleEvent`` get passed, this ``SimpleEvent`` will be
        interpreted as one MidiEvent (note_on and note_off) inside one
        MidiTrack inside one MidiFile.
        """

        midi_file = self._event_to_midi_file(event_to_convert)

        if path is not None:
            try:
                midi_file.save(filename=path)
            except Exception:
                raise AssertionError(midi_file)

        return midi_file
