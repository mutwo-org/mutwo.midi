with import <nixpkgs> {};
with pkgs.python3Packages;

let

  mutwo-core-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.core/archive/97aea97f996973955889630c437ceaea405ea0a7.tar.gz";
  mutwo-core = import (mutwo-core-archive + "/default.nix");

  mutwo-music-archive = builtins.fetchTarball "https://github.com/mutwo-org/mutwo.music/archive/4e4369c1c9bb599f47ec65eb86f87e9179e17d97.tar.gz";
  mutwo-music = import (mutwo-music-archive + "/default.nix");

in

  buildPythonPackage rec {
    name = "mutwo.midi";
    src = fetchFromGitHub {
      owner = "mutwo-org";
      repo = name;
      rev = "f7d2fec7fc3cc1149f23d410a3975729b8f36219";
      sha256 = "sha256-e6opdzs4gU1FYgAubvkpDT/fMjlzMxVxA5wmUgNekdQ=";
    };
    propagatedBuildInputs = [
      mutwo-core
      mutwo-music
      python39Packages.mido
      python39Packages.numpy
    ];
    doCheck = true;
  }
