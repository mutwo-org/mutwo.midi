with import <nixpkgs> {};
with pkgs.python310Packages;

let

  mutwo-core-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.core/archive/28a13e348876fa07929f5fd4f3953fee624c255c.tar.gz";
  mutwo-core = import (mutwo-core-archive + "/default.nix");

  mutwo-music-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.music/archive/725462d2342b0a27d88a38272b0ad93848d87399.tar.gz";
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
      mutwo-core
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
