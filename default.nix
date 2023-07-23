let
  sourcesTarball = fetchTarball "https://github.com/mutwo-org/mutwo-nix/archive/refs/heads/main.tar.gz";
  mutwo-midi = import (sourcesTarball + "/mutwo.midi/default.nix") {};
  mutwo-midi-local = mutwo-midi.overrideAttrs (
    finalAttrs: previousAttrs: {
       src = ./.;
    }
  );
in
  mutwo-midi-local

