"""Load midi files to mutwo"""

import abc
import typing

import mido

from mutwo import core_constants
from mutwo import core_converters
from mutwo import core_events
from mutwo import core_utilities
from mutwo import midi_converters
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


from mutwo import music_events


class MutwoParameterTupleToNoteLike(core_converters.abc.Converter):
    def convert(self, mutwo_parameter_tuple_to_convert) -> music_events.NoteLike:
        return music_events.NoteLike()


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
        raise NotImplementedError


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
        raise NotImplementedError


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
        raise NotImplementedError


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


class MidiFileToEvent(core_converters.abc.Converter):
    """Convert a midi file to a mutwo event.

    :param mutwo_parameter_tuple_to_simple_event: A callable which converts a
        tuple of mutwo parameters (duration, pitch list, volume) to a
        :class:`mutwo.core_events.SimpleEvent`. The default value generates
        :class:`mutwo.music_events.NoteLike`.
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
        mutwo_parameter_tuple_to_simple_event: typing.Callable[
            [
                tuple[
                    core_constants.DurationType,
                    list[music_parameters.abc.Pitch],
                    music_parameters.abc.Volume,
                ]
            ],
            core_events.SimpleEvent,
        ] = MutwoParameterTupleToNoteLike(),
        midi_pitch_to_mutwo_pitch: typing.Callable[
            [midi_converters.constants.MidiPitch], music_parameters.abc.Pitch
        ] = MidiPitchToMutwoMidiPitch(),
        midi_velocity_to_mutwo_volume: typing.Callable[
            [midi_converters.constants.MidiVelocity], music_parameters.abc.Volume
        ] = MidiVelocityToWesternVolume(),
    ):
        self._mutwo_parameter_tuple_to_simple_event = (
            mutwo_parameter_tuple_to_simple_event
        )
        self._midi_pitch_to_mutwo_pitch = midi_pitch_to_mutwo_pitch
        self._midi_velocity_to_mutwo_volume = midi_velocity_to_mutwo_volume

    def _midi_file_to_mutwo_event(
        self, midi_file_to_convert: mido.MidiFile
    ) -> core_events.abc.Event:
        for midi_track in midi_file_to_convert.tracks:
            pass

    def convert(
        self, midi_file_path_or_mido_midi_file: typing.Union[str, mido.MidiFile]
    ) -> core_events.abc.Event:
        """Convert midi file to mutwo event.

        :param midi_file_path_or_mido_midi_file: The midi file which shall
            be converted. Can either be a file name or a :class:`MidiFile`
            object from the `mido <https://github.com/mido/mido>`_ package.
        :type midi_file_path_or_mido_midi_file: typing.Union[str, mido.MidiFile]
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
                    " (from mido package)."
                )
            )
        return self._midi_file_to_mutwo_event(midi_file)
