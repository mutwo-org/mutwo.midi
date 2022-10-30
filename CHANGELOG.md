# Change Log

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](http://keepachangelog.com/)
and this project adheres to [Semantic Versioning](http://semver.org/).

## [Unreleased]

## [0.9.0] - 2022-30-12

### Changed
- `n_midi_channels_per_track` to `midi_channel_count_per_track`
- `EventToMidiFile.convert()` always returns a `mido.MidiFile`
- `EventToMidiFile.convert` can be called without any `path` argument (then it will simply return the `MidiFile` object, but don't write anything to disk).


## [0.8.0] - 2022-08-12

### Changed
- Package name from `mutwo.ext-midi` to `mutwo.midi`


## [0.6.0] - 2022-04-02

### Added
- backends module to convert midi files to mutwo event (experimental state):
    - `MidiFileToEvent`
    - `MidiVelocityToWesternVolume`
    - `MidiVelocityToMutwoVolume`
    - `MidiPitchToMutwoMidiPitch`
    - `MidiPitchToDirectPitch`
    - `MidiPitchToMutwoPitch`
    - `PitchBendingNumberToDirectPitchInterval`
    - `PitchBendingNumberToPitchInterval`


## [0.5.0] - 2022-03-11

### Changed
- some variables in `midi_converters.constants` to `midi_converters.configurations`

### Fixed
- slow calculation for glissandi / pitch envelopes


## [0.4.0] - 2022-01-30

### Changed
- package structure to namespace package to apply refactor of mutwo main package


## [0.3.0] - 2022-01-15

### Changed
- allow endless nested sequential events (if no simultaneous events occur in between)


## [0.2.0] - 2022-01-13

### Added
- support for pitch envelopes (allow glissandi now!)

### Changed
- applied movement from music related parameter and converter modules (which have been moved from [mutwo core](https://github.com/mutwo-org/mutwo) in version 0.49.0 to [mutwo.ext-music](https://github.com/mutwo-org/mutwo.ext-music))
