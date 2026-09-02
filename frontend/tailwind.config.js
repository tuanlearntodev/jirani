export default {
    content: ["./src/**/*.{js,jsx,ts,tsx}"], ,
  theme: {
    extend: {
      fontFamily: {
        display: ["'Playfair Display'", "serif"],
        body:    ["'IBM Plex Sans'", "sans-serif"],
        mono:    ["'IBM Plex Mono'", "monospace"],
      },
      colors: {
        black:        "#0A0A0A",
        card:         "#111111",
        border:       "#2a2a2a",
        gold:         "#C9A84C",
        "gold-light": "#E2C97E",
        "gold-dim":   "#7a5e20",
        text:         "#F0EAD6",
        muted:        "#7a7265",
        dim:          "#4a4540",
        danger:       "#c0392b",
        "danger-dim": "#2a1210",
      },
    },
  },
  plugins: [],
}