
import vte
import gtk
import pango
import os
import signal

window = gtk.Window(gtk.WINDOW_TOPLEVEL)
window.connect('destroy', lambda w: gtk.main_quit())
# initial window size
window.resize(640, 480)

terminal = vte.Terminal()
terminal.connect("child-exited", lambda w: gtk.main_quit())

# here you can set backscroll buffer
terminal.set_scrollback_lines(5000)
# encoding for console
terminal.set_encoding("UTF-8")
terminal.set_cursor_blinks(False)

# here you can set background image
#terminal.set_background_image_file("some/background/picture/here")

# transparency
terminal.set_opacity (45000)
# font for terminal
font = pango.FontDescription()
font.set_family("Ubuntu Mono")
# font size
font.set_size(11 * pango.SCALE)
font.set_weight(pango.WEIGHT_NORMAL)
font.set_stretch(pango.STRETCH_NORMAL)

terminal.set_font_full(font, True)

child_pid = terminal.fork_command()

scroll = gtk.ScrolledWindow()
scroll.set_policy(0,1)
scroll.add_with_viewport(terminal)

window.add(scroll)
window.show_all()

# This must be here! before gtk.main()
# here you can set columns count (first param)
terminal.set_size(500,0)

try:
    gtk.main()
except KeyboardInterrupt:
    pass