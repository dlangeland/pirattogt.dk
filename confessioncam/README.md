# ConfessionCam

*A kiosk for the guilty, the bold, and the rum-soaked*

---

Gather 'round, ye scallywags, and lend me both yer ears,  
Of pirates drunk on dark rum and their brine-encrusted fears.  
They sailed the seven oceans with a bottle and a blade,  
And when the rum ran low, matey — confessions must be made.

Old Captain Blacktooth Brennan had a secret in his chest,  
Not doubloons nor stolen jewels — nay, something far afield from best.  
He'd wept into his tankard every foggy Tuesday night,  
And kissed the ship's pet parrot in the pale bioluminescent light.

So step before the camera, let the lens see what you've done,  
Press the **Start** button, sailor — there's no hiding from the sun.  
The red light blinks its judgment as you stumble, stir, and sway,  
Press **Stop** when you are finished, or three minutes — then away.

The footage shall be captured, every hiccup, sob and slur,  
Preserved in glorious high-res, crystal-clear and crisp as her  
Cold eyes when she discovered what you'd spent the treasure on —  
Another cask of Barbados rum, and now the gold is gone.

Hold the **Quit** button three long seconds when you've had enough,  
When the seas of self-reflection get too existentially rough.  
The screen goes dark, the camera blinks, the parrot flies away —  
Even pirates need a power-off at the end of the day.

*Fair winds and following seas, ye wretched, rum-soaked souls.*

---

## Setup

```bash
cd ~/pirattogt/confessioncam
bash install.sh
cp /path/to/your/video.mp4 media/default_video.mp4
```

## Buttons (BCM numbering, connect other leg to GND)

| Button | GPIO | Action |
|--------|------|--------|
| Start  | 17   | Begin recording |
| Stop   | 27   | End recording, resume idle video |
| Quit   | 22   | Hold 3 s to shut down the app |

## Configuration

Edit `config.py` to adjust GPIO pins, resolution, recording timeout, bitrate, and idle video brightness.

Logs: `journalctl --user -u confessioncam -f`
