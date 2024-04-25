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
    "ChrononToControlMessageTuple",
    "CentDeviationToPitchBendingNumber",
    "MutwoPitchToMidiPitch",
    "EventToMidiFile",
)

ConvertableEvent = (
    core_events.Chronon
    | core_events.Consecution[core_events.Chronon]
    | core_events.Concurrence[core_events.Consecution[core_events.Chronon]]
)


class ChrononToControlMessageTuple(core_converters.ChrononToAttribute):
    """Convert :class:`mutwo.core_events.Chronon` to a tuple of control messages"""

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
        f = mutwo_pitch_to_convert.hertz
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

    :param chronon_to_pitch_list: Function to extract from a
        :class:`mutwo.core_events.Chronon` a tuple that contains pitch objects
        (objects that inherit from :class:`mutwo.music_parameters.abc.Pitch`).
        By default it asks the Event for its :attr:`pitch_list` attribute
        (because by default :class:`mutwo.music_events.NoteLike` objects are expected).
        When using different Event classes than ``NoteLike`` with a different name for
        their pitch property, this argument should be overridden. If the function call
        raises an :obj:`AttributeError` (e.g. if no pitch can be extracted),
        mutwo will interpret the event as a rest.
    :type chronon_to_pitch_list: typing.Callable[
            [core_events.Chronon], tuple[music_parameters.abc.Pitch, ...]]
    :param chronon_to_volume: Function to extract the volume from a
        :class:`mutwo.core_events.Chronon` in the purpose of generating midi notes.
        The function should return an object that inhertis from
        :class:`mutwo.music_parameters.abc.Volume`. By default it asks the Event for
        its :attr:`volume` attribute (because by default
        :class:`mutwo.music_events.NoteLike` objects are expected).
        When using different Event classes than ``NoteLike`` with a
        different name for their volume property, this argument should be overridden.
        If the function call raises an :obj:`AttributeError` (e.g. if no volume can be
        extracted), mutwo will interpret the event as a rest.
    :type chronon_to_volume: typing.Callable[
            [core_events.Chronon], music_parameters.abc.Volume]
    :param chronon_to_control_message_tuple: Function to generate midi control messages
        from a chronon. By default no control messages are generated. If the
        function call raises an AttributeError (e.g. if an expected control value isn't
        available) mutwo will interpret the event as a rest.
    :type chronon_to_control_message_tuple: typing.Callable[
            [core_events.Chronon], tuple[mido.Message, ...]]
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
        :class:`~mutwo.core_events.Consecution` is passed to the convert method.
        If set to ``True`` each :class:`~mutwo.core_events.Consecution`
        only makes use of exactly n_midi_channel (see next parameter).
        If set to ``False`` each converted :class:`Consecution` is allowed to make use of all
        available channels. If set to ``True`` and the amount of necessary MidiTracks is
        higher than the amount of available channels, mutwo will silently cycle through
        the list of available midi channel.
    :type distribute_midi_channels: bool
    :param midi_channel_count_per_track: This parameter is only relevant for
        distribute_midi_channels == True. It sets how many midi channels are assigned
        to one Consecution. If microtonal chords shall be played by
        one Consecution (via pitch bending messages) a higher number than 1 is
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
    :param tempo: All Midi files should specify their tempo. The default
        value of mutwo is 120 BPM (this is also the value that is assumed by any
        midi-file-reading-software if no tempo has been specified). Tempo changes
        are supported (and will be written to the resulting midi file).
    :type tempo: core_parameters.abc.Tempo

    **Example**:

    >>> from mutwo import midi_converters
    >>> from mutwo import music_parameters
    >>> # midi file converter that assign a middle c to all events
    >>> midi_converter = midi_converters.EventToMidiFile(
    ...     chronon_to_pitch_list=lambda event: (music_parameters.WesternPitch('c'),)
    ... )

    **Disclaimer**:
        The current implementation doesn't support time-signatures (the written time
        signature is always 4/4 for now).
    """

    def __init__(
        self,
        chronon_to_pitch_list: typing.Callable[
            [core_events.Chronon], tuple[music_parameters.abc.Pitch, ...]
        ] = music_converters.ChrononToPitchList(),  # type: ignore
        chronon_to_volume: typing.Callable[
            [core_events.Chronon], music_parameters.abc.Volume
        ] = music_converters.ChrononToVolume(),  # type: ignore
        chronon_to_control_message_tuple: typing.Callable[
            [core_events.Chronon], tuple[mido.Message, ...]
        ] = ChrononToControlMessageTuple(),
        midi_file_type: int = None,
        available_midi_channel_tuple: tuple[int, ...] = None,
        distribute_midi_channels: bool = False,
        midi_channel_count_per_track: typing.Optional[int] = None,
        mutwo_pitch_to_midi_pitch: MutwoPitchToMidiPitch = MutwoPitchToMidiPitch(),
        ticks_per_beat: typing.Optional[int] = None,
        instrument_name: typing.Optional[str] = None,
        tempo: typing.Optional[core_parameters.abc.Tempo] = None,
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
        self._tempo = tempo or midi_converters.configurations.DEFAULT_TEMPO
        self._chronon_to_pitch_list = chronon_to_pitch_list
        self._chronon_to_volume = chronon_to_volume
        self._chronon_to_control_message_tuple = chronon_to_control_message_tuple
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
        tempo_point: core_constants.Real | core_parameters.DirectTempo,
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
        bl_in_seconds = core_parameters.DirectTempo(beats_per_minute).seconds
        return int(bl_in_seconds * midi_converters.constants.MIDI_TEMPO_FACTOR)

    def _find_available_midi_channel_tuple_per_consecution(
        self,
        concurrence: core_events.Concurrence[
            core_events.Consecution[core_events.Chronon]
        ],
    ) -> tuple[tuple[int, ...], ...]:
        """Find midi channels for each Consecution.

        Depending on whether distribute_midi_channels has been set
        to True this method distributes all available midi channels
        on the respective Consecutions.
        """
        if self._distribute_midi_channels:
            mchannel_cycle = itertools.cycle(self._available_midi_channel_tuple)
            return tuple(
                tuple(
                    next(mchannel_cycle)
                    for _ in range(self._midi_channel_count_per_track)
                )
                for _ in concurrence
            )
        else:
            return tuple(self._available_midi_channel_tuple for _ in concurrence)

    def _beats_to_ticks(self, absolute_time: core_parameters.abc.Duration.Type) -> int:
        abs_t = core_parameters.abc.Duration.from_any(absolute_time)
        return int(self._ticks_per_beat * abs_t.beat_count)

    # ###################################################################### #
    #             methods for converting mutwo data to midi data             #
    # ###################################################################### #

    def _tempo_to_midi_message_tuple(
        self, tempo: core_parameters.abc.Tempo
    ) -> tuple[mido.MetaMessage, ...]:
        """Converts a Consecution of ``EnvelopeEvent`` to midi Tempo messages."""

        if isinstance(tempo, core_parameters.FlexTempo):
            tempo_envelope = tempo
        else:
            tempo_envelope = core_parameters.FlexTempo([[0, tempo]])

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
        # Simple case: we don't have any glissando
        if not isinstance(pitch_to_tune, music_parameters.FlexPitch):
            midi_pitch, pitch_bend = self._mutwo_pitch_to_midi_pitch.convert(
                pitch_to_tune
            )
            return midi_pitch, (
                mido.Message(
                    "pitchwheel",
                    channel=midi_channel,
                    pitch=pitch_bend,
                    # If possible add bending one tick earlier to avoid glitches
                    time=absolute_tick_start - 1
                    if absolute_tick_start
                    else absolute_tick_start,
                ),
            )

        tick_count = absolute_tick_end - absolute_tick_start

        # We have to use one tick less, so that at
        # "pitch_to_tune.value_at(tick_count)" we already reached the
        # end of the envelope.
        #
        # XXX: Should we really set the envelope to the full duration of the event?
        # Because it could be that our event is shorter/longer than the glissando.
        # And this should actually be reflected here!
        #
        # => TODO We should fix this in an earlier state.
        f = pitch_to_tune.copy()
        f.duration = tick_count - 1

        # Convert the pitch envelope to numerical values for better performance
        fnumerical = core_events.Envelope(
            [
                [absolute_time, value, event.curve_shape]
                for absolute_time, value, event in zip(
                    f.absolute_time_tuple, f.value_tuple, f
                )
            ]
        )

        # Find center pitch, so that we can cover as many intervals
        # as possible.
        value_tuple = fnumerical.value_tuple
        min_hertz, max_hertz = min(value_tuple), max(value_tuple)
        center_hertz = (
            music_parameters.DirectPitch(min_hertz)
            + music_parameters.DirectPitchInterval(
                music_parameters.abc.Pitch.hertz_to_cents(min_hertz, max_hertz) * 0.5
            )
        ).hertz
        midi_pitch, pitch_bend = self._mutwo_pitch_to_midi_pitch.convert(
            music_parameters.DirectPitch(center_hertz)
        )

        fcent_numerical = core_events.Envelope(
            [
                [
                    absolute_time,
                    music_parameters.abc.Pitch.hertz_to_cents(center_hertz, p.value),
                    p.curve_shape,
                ]
                for absolute_time, p in zip(fnumerical.absolute_time_tuple, fnumerical)
            ]
        )

        pbm_list = []
        for t in range(0, tick_count):
            cent_deviation = fcent_numerical.value_at(t)
            pb = self._mutwo_pitch_to_midi_pitch._cent_deviation_to_pitch_bending_number.convert(
                cent_deviation
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
        duration: core_parameters.abc.Duration.Type,
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
        duration = core_parameters.abc.Duration.from_any(duration)
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

    def _chronon_to_midi_message_tuple(
        self,
        chronon: core_events.Chronon,
        absolute_time: core_parameters.abc.Duration,
        available_midi_channel_tuple_cycle: typing.Iterator,
    ) -> tuple[mido.Message, ...]:
        """Converts ``Chronon`` (or any object that inherits from ``Chronon``).

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
            ("pitch_list", self._chronon_to_pitch_list),
            ("volume", self._chronon_to_volume),
            ("control_message_tuple", self._chronon_to_control_message_tuple),
        ):
            try:
                d = extraction_function(chronon)
            except AttributeError:
                is_rest = True
            else:
                if d is None:
                    self._logger.warning(
                        "Extracting '{p}' from event '{chronon}' "
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
            chronon.duration,
            available_midi_channel_tuple_cycle,
            *extracted_data_list,  # type: ignore
        )

    def _consecution_to_midi_message_tuple(
        self,
        consecution: core_events.Consecution[
            core_events.Chronon | core_events.Consecution
        ],
        available_midi_channel_tuple: tuple[int, ...],
        absolute_time: core_parameters.abc.Duration = core_parameters.DirectDuration(0),
    ) -> tuple[mido.Message, ...]:
        """Iterates through the ``Consecution`` and converts each ``Chronon``.

        Return unsorted tuple of Midi messages where the time attribute of each message
        is the absolute time in ticks.
        """

        mlist: list[mido.Message] = []
        mchannel_cycle = itertools.cycle(available_midi_channel_tuple)

        # fill midi track with the content of the consecution
        for local_abs_time, sim_or_seq in zip(
            consecution.absolute_time_tuple, consecution
        ):
            global_abs_time = local_abs_time + absolute_time
            if isinstance(sim_or_seq, core_events.Chronon):
                mtuple = self._chronon_to_midi_message_tuple(
                    sim_or_seq, global_abs_time, mchannel_cycle
                )
                self._logger.debug(
                    f"Chronon -> MidiMessageData:\n\t{sim_or_seq} -> {mtuple}"
                )
            else:
                mtuple = self._consecution_to_midi_message_tuple(
                    sim_or_seq,
                    available_midi_channel_tuple,
                    global_abs_time,
                )
            mlist.extend(mtuple)

        return tuple(mlist)

    def _midi_message_tuple_to_midi_track(
        self,
        midi_message_tuple: tuple[mido.Message | mido.MetaMessage, ...],
        duration: core_parameters.abc.Duration.Type,
        is_first_track: bool = False,
    ) -> mido.MidiTrack:
        """Convert unsorted midi message with absolute timing to a midi track.

        In the resulting midi track the timing of the messages is relative.
        """
        duration = core_parameters.abc.Duration.from_any(duration)
        self._logger.debug(
            "Convert midi messages -> MidiTrack\n\t" f"msg-tuple: {midi_message_tuple}"
        )

        track = mido.MidiTrack([])
        track.append(mido.MetaMessage("instrument_name", name=self._instrument_name))

        if is_first_track:
            # standard time signature 4/4
            track.append(mido.MetaMessage("time_signature", numerator=4, denominator=4))
            midi_message_tuple += self._tempo_to_midi_message_tuple(self._tempo)

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

    def _add_chronon_to_midi_file(
        self, chronon: core_events.Chronon, midi_file: mido.MidiFile
    ) -> None:
        self._add_consecution_to_midi_file(
            core_events.Consecution([chronon]), midi_file
        )

    def _add_consecution_to_midi_file(
        self,
        consecution: core_events.Consecution[core_events.Chronon],
        midi_file: mido.MidiFile,
    ) -> None:
        self._add_concurrence_to_midi_file(
            core_events.Concurrence([consecution]), midi_file
        )

    def _add_concurrence_to_midi_file(
        self,
        concurrence: core_events.Concurrence[
            core_events.Consecution[core_events.Chronon]
        ],
        midi_file: mido.MidiFile,
    ) -> None:
        # Depending on the midi_file_type either adds a tuple of MidiTrack
        # objects (for midi_file_type = 1) or adds only one MidiTrack
        # (for midi_file_type = 0).
        midi_channel_data = self._find_available_midi_channel_tuple_per_consecution(
            concurrence
        )
        midi_data_per_seq_tuple = tuple(
            self._consecution_to_midi_message_tuple(seq, m)
            for seq, m in zip(concurrence, midi_channel_data)
        )
        duration = concurrence.duration

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
            case core_events.Concurrence():
                self._logger.debug("Concurrence -> MidiFile")
                self._add_concurrence_to_midi_file(event_to_convert, midi_file)
            case core_events.Consecution():
                self._logger.debug("Consecution -> MidiFile")
                self._add_consecution_to_midi_file(event_to_convert, midi_file)
            case core_events.Chronon():
                self._logger.debug("Chronon -> MidiFile")
                self._add_chronon_to_midi_file(event_to_convert, midi_file)
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
        :type event_to_convert: core_events.Chronon | core_events.Consecution[core_events.Chronon] | core_events.Concurrence[core_events.Consecution[core_events.Chronon]]
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
        >>> ascending_scale = core_events.Consecution(
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
        structure is a :class:`mutwo.core_events.Concurrence` (representing
        the complete MidiFile) that contains :class:`mutwo.core_events.Consecution`
        (where each ``Consecution`` represents one MidiTrack) that contains
        :class:`mutwo.core_events.Chronon` (where each ``Chronon``
        represents one midi note). If only one ``Consecution`` is send,
        this ``Consecution`` will be read as one MidiTrack in a MidiFile.
        If only one ``Chronon`` get passed, this ``Chronon`` will be
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
