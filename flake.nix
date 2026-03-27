{
  description = "Miniswarm — multi-agent collaboration via local IRC";

  inputs = {
    nixpkgs.url = "github:NixOS/nixpkgs/nixpkgs-unstable";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { self, nixpkgs, flake-utils }:
    flake-utils.lib.eachDefaultSystem (system:
      let
        pkgs = nixpkgs.legacyPackages.${system};

        # Minimal ngircd config for the swarm
        swarmConfig = pkgs.writeText "ngircd-swarm.conf" ''
          [Global]
              Name = swarm.local
              Info = Miniswarm IRC Server
              Listen = 127.0.0.1
              Ports = 6667

          [Limits]
              MaxConnections = 50
              MaxNickLength = 30

          [Options]
              PAM = no

          [Channel]
              Name = #swarm
              Topic = Miniswarm coordination channel — all agents report here
              Modes = tn
        '';

        # Wrapper script to launch ngircd with our config
        swarm-server = pkgs.writeShellScriptBin "swarm-server" ''
          PORT="''${SWARM_PORT:-6667}"
          HOST="127.0.0.1"

          if ${pkgs.netcat-gnu}/bin/netcat -z "$HOST" "$PORT" 2>/dev/null; then
              echo "IRC server already running on $HOST:$PORT"
              exit 0
          fi

          echo "Starting ngircd on $HOST:$PORT ..."
          exec ${pkgs.ngircd}/bin/ngircd -f ${swarmConfig} -n
        '';

        # Wrapper for ii (filesystem-based IRC client)
        swarm-connect = pkgs.writeShellScriptBin "swarm-connect" ''
          NICK="''${1:?Usage: swarm-connect <nick> [channel] [host] [port]}"
          CHANNEL="''${2:-#swarm}"
          HOST="''${3:-127.0.0.1}"
          PORT="''${4:-6667}"

          FIFO="/tmp/irc-fifo-''${NICK}"
          LOG="/tmp/irc-log-''${NICK}.txt"

          cleanup() {
              rm -f "$FIFO"
              [ -n "''${IRC_PID:-}" ] && kill "$IRC_PID" 2>/dev/null || true
              echo "Disconnected $NICK from $HOST:$PORT"
          }
          trap cleanup EXIT

          rm -f "$FIFO"
          ${pkgs.coreutils}/bin/mkfifo "$FIFO"

          ${pkgs.coreutils}/bin/tail -f "$FIFO" \
            | ${pkgs.netcat-gnu}/bin/netcat "$HOST" "$PORT" > "$LOG" 2>&1 &
          IRC_PID=$!

          sleep 0.5

          echo -e "NICK $NICK\r" > "$FIFO"
          echo -e "USER $NICK 0 * :$NICK agent\r" > "$FIFO"
          sleep 0.5
          echo -e "JOIN $CHANNEL\r" > "$FIFO"
          sleep 0.3
          echo -e "PRIVMSG $CHANNEL :HELLO — $NICK is online and ready.\r" > "$FIFO"

          echo "Connected as $NICK to $CHANNEL on $HOST:$PORT"
          echo "Send:    echo 'PRIVMSG $CHANNEL :your message' > $FIFO"
          echo "Receive: tail -f $LOG"
          echo ""
          echo "Keeping connection alive (Ctrl-C to disconnect)..."

          ${pkgs.coreutils}/bin/tail -f "$LOG" | while IFS= read -r line; do
              if [[ "$line" == PING* ]]; then
                  PONG="''${line/PING/PONG}"
                  echo -e "''${PONG}\r" > "$FIFO"
              fi
          done
        '';

        # Human-friendly IRC client, pre-configured for #swarm
        swarm-chat = pkgs.writeShellScriptBin "swarm-chat" ''
          NICK="''${1:-$USER}"
          HOST="''${2:-localhost}"
          PORT="''${3:-6667}"
          exec ${pkgs.irssi}/bin/irssi -c "$HOST" -p "$PORT" -n "$NICK"
        '';

      in {
        # `nix develop` — drop into a shell with all tools available
        devShells.default = pkgs.mkShell {
          name = "miniswarm";
          packages = [
            pkgs.ngircd        # IRC server
            pkgs.ii             # Filesystem-based IRC client
            pkgs.irssi          # Full IRC client (for humans)
            pkgs.netcat-gnu     # For raw TCP connections
            swarm-server        # `swarm-server` command
            swarm-connect       # `swarm-connect <nick>` command
            swarm-chat          # `swarm-chat [nick]` — irssi for humans
          ];

          shellHook = ''
            echo "=== Miniswarm dev shell ==="
            echo "  swarm-server          Start the IRC server"
            echo "  swarm-connect <nick>  Connect as an agent"
            echo "  swarm-chat [nick]     Connect as a human (irssi)"
            echo ""
            mkdir -p /tmp/swarm-share
          '';
        };

        # `nix run` — start the server directly
        apps.default = {
          type = "app";
          program = "${swarm-server}/bin/swarm-server";
        };

        # `nix run .#connect` — connect helper
        apps.connect = {
          type = "app";
          program = "${swarm-connect}/bin/swarm-connect";
        };

        # `nix run .#chat` — human IRC client (irssi)
        apps.chat = {
          type = "app";
          program = "${swarm-chat}/bin/swarm-chat";
        };

        packages = {
          default = swarm-server;
          server = swarm-server;
          connect = swarm-connect;
          chat = swarm-chat;
        };
      }
    );
}
