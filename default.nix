with import <nixpkgs> {};
with pkgs.python310Packages;

let

  mutwo-music-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.music/archive/929ec3faadd6426356d27df9614143e641be745d.tar.gz";
  mutwo-music = import (mutwo-music-archive + "/default.nix");

in

  buildPythonPackage rec {
    name = "mutwo.midi";
    src = fetchFromGitHub {
      owner = "mutwo-org";
      repo = name;
      rev = "156b25cdad7b47c97783569bf6819a7ab5d5ee10";
      sha256 = "sha256-Yqk+E9E9I4oUn4yx4hWwnSf43dYHbbMPy+djVGms3tw=";
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
