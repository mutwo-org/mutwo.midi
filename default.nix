with import <nixpkgs> {};
with pkgs.python310Packages;

let

  mutwo-music-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.music/archive/ed79ca5e3fc169ed3dc4ad62189ec001626d94ea.tar.gz";
  mutwo-music = import (mutwo-music-archive + "/default.nix");

in

  buildPythonPackage rec {
    name = "mutwo.midi";
    src = fetchFromGitHub {
      owner = "mutwo-org";
      repo = name;
      rev = "5cf9609b84fb51811bc3d746b32e40e325427a4d";
      sha256 = "sha256-dgnV3DbDFMCCrst9lfYDXoRz0RW+2jGNhZ6e4YoVkc4=";
    };
    checkInputs = [
      python310Packages.pytest
    ];
    propagatedBuildInputs = [
      mutwo-music
      python310Packages.mido
      python310Packages.numpy
    ];
    checkPhase = ''
      runHook preCheck
      pytest
      runHook postCheck
    '';
    doCheck = true;
  }
