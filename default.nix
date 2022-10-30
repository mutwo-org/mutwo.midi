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
      rev = "82c81a215c406aae2724ada3033c4ffabc105aff";
      sha256 = "sha256-hQzj8S2PNKYjcPhc5kvHKTjgBc20tdsN+4iHhWhHl9Y=";
    };
    propagatedBuildInputs = [
      mutwo-core
      mutwo-music
      python39Packages.mido
      python39Packages.numpy
    ];
    doCheck = true;
  }
