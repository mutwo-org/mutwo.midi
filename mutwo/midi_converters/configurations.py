"""Configure the midi converters behaviour"""

from mutwo import core_events
from mutwo import core_parameters

DEFAULT_AVAILABLE_MIDI_CHANNEL_TUPLE = tuple(range(16))
"""default value for ``available_midi_channel_tuple`` in `MidiFileConverter`"""

DEFAULT_MAXIMUM_PITCH_BEND_DEVIATION_IN_CENTS = 200
"""default value for ``maximum_pitch_bend_deviation_in_cents`` in `MidiFileConverter`"""

DEFAULT_MIDI_FILE_TYPE = 1
"""default value for ``midi_file_type`` in `MidiFileConverter`"""

DEFAULT_MIDI_INSTRUMENT_NAME = "Acoustic Grand Piano"
"""default value for ``midi_instrument_name`` in `MidiFileConverter`"""

DEFAULT_N_MIDI_CHANNELS_PER_TRACK = 1
"""default value for ``n_midi_channels_per_track`` in `MidiFileConverter`"""

DEFAULT_TEMPO_ENVELOPE: core_events.TempoEnvelope = core_events.TempoEnvelope(
    ((0, core_parameters.TempoPoint(120, 1)), (1, core_parameters.TempoPoint(120, 1))),
)
"""default value for ``tempo_envelope`` in `MidiFileConverter`"""

DEFAULT_TICKS_PER_BEAT = 480
"""default value for ``ticks_per_beat`` in `MidiFileConverter`"""

DEFAULT_CONTROL_MESSAGE_TUPLE_ATTRIBUTE_NAME = "control_message_tuple"
"""The expected attribute name of a :class:`mutwo.core_events.SimpleEvent` for control messages."""


del core_events, core_parameters
