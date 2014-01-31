#!/usr/bin/python3

import sys, os, subprocess, codecs, signal, shutil, time, json, gettext, traceback


# Config
DEBUG = False

PACKAGE = '@PACKAGE@'
SYSCONFDIR = '@SYSCONFDIR@'
LOCALEDIR = '@LOCALEDIR@'
PKGVARDIR = '@PKGVARDIR@'
TMPDIR = os.path.join(PKGVARDIR, 'tmp')
IMGDIR = os.path.join(PKGVARDIR, 'images')


# gettext
gettext.bindtextdomain(PACKAGE, LOCALEDIR)
gettext.textdomain(PACKAGE)
_ = gettext.gettext


# format_exception:
#
def format_exception (exc_info=None) :
    tp, exc, tb = \
      sys.exc_info() if exc_info is None \
      else exc_info
    lines = [('%s:%d:%s:' % (fn, ln, fc), co)
             for fn, ln, fc, co in traceback.extract_tb(tb)]
    cw = [max(len(l[c]) for l in lines) for c in range(2)]
    msg = '%s: %s\n' % (tp.__name__, exc)
    if len(msg) > 200 : msg = msg[:197] + '...'
    sep1 = ('=' * max(len(msg) - 1, (sum(cw) + 4))) + '\n'
    sep2 = ('-' * max(len(msg) - 1, (sum(cw) + 4))) + '\n'
    plines = [sep1, msg, sep2]
    plines.extend('%s%s -- %s\n' %
                  (l[0], (' ' * (cw[0] - len(l[0]))), l[1])
                  for l in reversed(lines))
    plines.append(sep1)
    return plines


# print_exception:
#
def print_exception (exc_info=None, f=None) :
    if f is None : f = sys.stderr
    f.writelines(format_exception(exc_info))


# trace:
#
def trace (msg) :
    sys.stderr.write('windump: %s\n' % msg)
    sys.stderr.flush()


# convdate:
#
def convdate (dt) :
    return time.strftime('%c', time.strptime(dt, '%Y/%m/%d %H:%M:%S'))


# screen_reset:
#
def screen_reset () :
    subprocess.check_call(['reset'])


# _mkdir:
#
def _mkdir (d) :
    if os.path.isdir(d) :
        return
    _mkdir(os.path.dirname(d))
    trace("creating directory '%s'" % d)
    os.mkdir(d)


# human_size:
#
def human_size (s) :
    for n, u in enumerate(('B', 'K', 'M', 'G', 'T')) :
        if s < 1000 * (1024 ** n) :
            break
    if n == 0 :
        return '%d%s' % (s, u)
    else :
        s = s / (1024 ** n)
        return '%.3f%s' % (s, u)


# devcanon:
#
def devcanon (d) :
    if d.startswith('UUID=') :
        uuid = d.split('=', 1)[1]
        d = os.path.join('/dev/disk/by-uuid', d)
    elif d.startswith('LABEL=') :
        assert 0, "[TODO] %s" % d
    d = os.path.realpath(d)
    if os.path.exists(d) : return d
    else : return ''

    
# deveq:
#
def deveq (d1, d2) :
    return devcanon(d1) == devcanon(d2)


# ismounted:
#
def ismounted (dev_) :
    dev = os.path.realpath(dev_)
    assert os.path.exists(dev), dev_
    minfo = subprocess.check_output(['mount'], universal_newlines=True)
    for line in minfo.split('\n') :
        line = line.strip()
        if not line : continue
        mdev = line.split()[0]
        if deveq(dev, mdev) :
            return True
    return False

    
# umount:
#
def umount (dev_) :
    dev = os.path.realpath(dev_)
    assert os.path.exists(dev), dev_
    if not ismounted(dev) :
        return True
    trace("unmounting device '%s'" % dev)
    proc = subprocess.Popen(['umount', dev], stderr=subprocess.PIPE,
                            universal_newlines=True)
    err = proc.stderr.read().strip()
    r = proc.wait()
    if r == 0 :
        trace("OK")
        return True
    else :
        text = (_("ERROR") + ": " + _("could not unmount device '%(dev)s'") + "\n\n" +
                err + "\n\n" +
                "(" + _("close any application using it and try again") +
                " - " + _("if it does not help, try to restart the computer") + ")") \
                % {'dev': dev}
        dlg_error(text=text)
        return False


# mount:
#
def mount (dev_) :
    dev = os.path.realpath(dev_)
    assert os.path.exists(dev), dev_
    if ismounted(dev) :
        return
    found = False
    for line in open('/etc/fstab', 'rt') :
        line = line.strip()
        if (not line) or line[0] == '#' :
            continue
        mdev = line.split()[0]
        if deveq(dev, mdev) :
            found = True
            break
    if not found :
        return
    proc = subprocess.Popen(['mount', dev], stderr=subprocess.PIPE,
                            universal_newlines=True)
    err = proc.stderr.read().strip()
    r = proc.wait()
    if r == 0 :
        return True
    else :
        text = (_("ERROR") + ": " + _("could not remount device '%(dev)s'")) \
          % {'dev': dev}
        dlg_error(text=text)
        return False


# dialog:
#
def dialog (widget, title=None, extra=None) :
    if title is None : title = PACKAGE.upper()
    else : title = '%s: %s' % (PACKAGE.upper(), title)
    cmd = ['dialog', '--title', title]
    if extra is not None :
        cmd.extend(extra)
    cmd.extend(widget)
    proc = subprocess.Popen(cmd, stderr=subprocess.PIPE)
    out = proc.stderr.read().decode().strip()
    r = proc.wait()
    if r != 0 and out :
        trace("dialog error: %s" % out)
    return r, out


# dlg_yesno:
#
def dlg_yesno (text, **kwargs) :
    return dialog(widget=['--yesno', text, '0', '0'], **kwargs)


# dlg_menu:
#
def dlg_menu (text, menu, menu_height=None, **kwargs) :
    if menu_height is None :
        menu_height = min(20, len(menu))
    w = ['--menu', text, '0', '0', str(menu_height)]
    for i in menu :
        w.extend(i)
    return dialog(widget=w, **kwargs)


# dlg_inputbox:
#
def dlg_inputbox (text, init='', **kwargs) :
    w = ['--inputbox', text, '0', '0', init]
    return dialog(widget=w, **kwargs)


# dlg_msgbox:
#
def dlg_msgbox (text, **kwargs) :
    return dialog(widget=['--msgbox', text, '0', '0'], **kwargs)


# dlg_error:
#
def dlg_error (text, **kwargs) :
    kwargs.setdefault('title', _('ERROR'))
    return dlg_msgbox(text=text, **kwargs)


# dev_by_uuid:
#
def dev_by_uuid (uuid, defo='') :
    f = os.path.join('/dev/disk/by-uuid', uuid)
    if os.path.exists(f) : return os.path.realpath(f)
    else : return defo


# label_by_uuid:
#
def label_by_uuid (uuid, defo='<?>') :
    dev = dev_by_uuid(uuid)
    if not dev : return '<?>'
    for label in os.listdir('/dev/disk/by-label') :
        if os.path.realpath(os.path.join('/dev/disk/by-label', label)) == dev :
            return label
    return defo
    


# list_devices:
#
def list_devices () :
    l = []
    for uuid in os.listdir('/dev/disk/by-uuid') :
        if uuid in BLACKLIST :
            continue
        dev = dev_by_uuid(uuid)
        label = label_by_uuid(uuid)
        l.append((dev, label, uuid))
    return l


# devinfo:
#
def devinfo (dev) :
    info = ((_("DEV"), dev[0]),
            (_("LABEL"), dev[1]),
            (_("UUID"), dev[2]))
    w = max(len(i[0]) for i in info)
    text = '\n'.join(('%s %s %s' % (i[0], ('_' * (w-len(i[0]))), i[1]))
                     for i in info)
    trace("devinfo:\n%s" % text)
    return text


# imginfo:
#
def imginfo (imgname) :
    return json.load(open(os.path.join(IMGDIR, imgname, 'info.txt'), 'rt'))


# imgsize:
#
def imgsize (imgname) :
    d = os.path.join(IMGDIR, imgname)
    n, s = 0, 0
    while True :
        f = os.path.join(d, 'fsimage.%03d' % n)
        if not os.path.exists(f) :
            break
        s += os.stat(f).st_size
        n += 1
    return s


# select_device:
#
def select_device (devlist=None) :
    if devlist is None :
        devlist = list_devices()
    else :
        devlist = list(devlist)
    if not devlist :
        dlg_msgbox(_("No device found"))
        return ''
    # select partition
    text = _("Please choose a partition")
    devlist.sort(key=lambda d: d[0])
    lw = max(len(d[1]) for d in devlist)
    menu=tuple((d[0], '| %s%s | %s' % (d[1], (' ' * (lw-len(d[1]))), d[2]))
               for d in devlist)
    r, out = dlg_menu(text, menu=menu)
    if r != 0 : return None
    dev, = [d for d in devlist if d[0] == out]
    return dev


# list_images:
#
def list_images (uuid=None) :
    l = []
    for img in os.listdir(IMGDIR) :
        imgdir = os.path.join(IMGDIR, img)
        if not os.path.isdir(imgdir) : continue
        if uuid is None or uuid == imginfo(img)['uuid'] :
            l.append(img)
    return l


# select_image:
#
def select_image (create=False, defname='', uuid=None) :
    imglist = list_images(uuid=uuid)
    imgname = ''
    while not imgname :
        if imglist :
            idescr = [(i, imginfo(i)['date'], convdate(imginfo(i)['date'])) for i in imglist]
            idescr.sort(key=lambda i: i[1], reverse=True)
            menu = [(str(n+1), '%s | %s' % (i[2], i[0]))
                    for n, i in enumerate(idescr)]
            if create : menu = [('0', _("new image"))] + menu
            text = _("Please choose an image")
            r, out = dlg_menu(text=text, menu=menu)
            if r != 0 : return ''
            out = int(out) - 1
            if out >= 0 :
                imgname = idescr[out][0]
        if not imgname :
            if not create :
                dlg_msgbox(_("No image found"))
                return ''
            r, out = dlg_inputbox(text=_("Choose a name for this backup"), init=defname)
            if r != 0 : return ''
            trace("OUT: '%s'" % out)
            imgname = out
    return imgname


# proc_backup:
#
def proc_backup () :
    # choose a device
    dev = select_device()
    if not dev : return
    # choose an image name
    defname = '%s_' % (dev[1] if dev[1] else dev[2])
    imgname = select_image(create=True, defname=defname, uuid=dev[2])
    if not imgname : return
    
    # check existing and ask confirmation
    imgdir = os.path.join(IMGDIR, imgname)
    if os.path.exists(imgdir) :
        warn = _("WARNING: THIS IMAGE ALREADY EXISTS AND WILL BE OVERWRITTEN BY THIS ONE!")
    else :
        warn = _("(New image)")
    text = (devinfo(dev) + "\n\n" +
            _("IMAGE: %(img)s") + "\n\n" +
            "%(warn)s\n\n" +
            _("Do you want to continue ?")) \
            % {'img': imgname, 'warn': warn}
    r, out = dlg_yesno(text=text, extra=['--defaultno'])
    if r != 0 : return

    # go
    tmpdir = os.path.join(TMPDIR, imgname)
    assert not os.path.exists(tmpdir), tmpdir
    _mkdir(tmpdir)
    # write infos
    json.dump({'uuid': dev[2], 'label': dev[1],
               'date': time.strftime('%Y/%m/%d %H:%M:%S')},
              open(os.path.join(tmpdir, 'info.txt'), 'wt'))
    # dump
    tmpfile = os.path.join(tmpdir, 'fsimage')
    cmd = ['/usr/sbin/partimage', '--batch', '--compress=%d' % COMPRESS,
           '--volume=%s' % VOLUME, '--nodesc', '--finish=0',
           'save', dev[0], tmpfile]

    # umount if needed
    if not umount(dev[0]) :
        return
    try:
        trace("> %s" % ' '.join(cmd))
        proc = subprocess.Popen(cmd)
        r = proc.wait()
    finally:
        mount(dev[0])
    trace("R: %s" % r)
    if r == 0 :
        if os.path.exists(imgdir) :
            shutil.rmtree(imgdir)
        os.rename(tmpdir, imgdir)
        dlg_msgbox(_("Image '%(i)s' created succesfully") % {'i': imgname})
    else :
        shutil.rmtree(tmpdir)
        dlg_error(_("Image creation failed!"))


# proc_restore:
#
def proc_restore () :
    trace("PROC_RESTORE")
    uuidlist = set(imginfo(i)['uuid'] for i in list_images())
    if not uuidlist :
        dlg_msgbox(_("No backup found"))
        return

    devlist = ((dev_by_uuid(uuid, defo=_("<none>")), label_by_uuid(uuid), uuid)
               for uuid in uuidlist)
    dev = select_device(devlist=devlist)
    trace("dev: %s" % repr(dev))
    if not dev : return
    if not os.path.exists(os.path.join('/dev/disk/by-uuid', dev[2])) :
        dlg_msgbox(_("Device '%(uuid)s' is not present") %
                  {'uuid': dev[2]})
        return

    imgname = select_image(uuid=dev[2])
    trace("image: '%s'" % imgname)
    if not imgname : return
    # just in case
    assert imginfo(imgname)['uuid'] == dev[2], imgname
    
    text = (devinfo(dev) + "\n\n" +
            _("IMAGE: %(img)s") + "\n\n" +
            _("WARNING: THIS OPERATION WILL ERASE ALL DATAS ON THIS PARTITION!") + "\n\n" +
            _("Do you want to continue ?")) \
            % {'img': imgname}
    r, out = dlg_yesno(text=text, extra=['--defaultno'])
    if r != 0 : return

    trace("umount")
    if umount(dev[0]) :
        trace("umount OK")
    else :
        trace("umount failed")
        return

    imgfile = os.path.join(IMGDIR, imgname, 'fsimage.000')
    cmd = ['/usr/sbin/partimage', '--batch', 'restore', dev[0], imgfile]
    try:
        trace("> %s" % ' '.join(cmd))
        proc = subprocess.Popen(cmd)
        r = proc.wait()
        trace("r: %s" % r)
    finally:
        trace("mount")
        if mount(dev[0]) :
            trace("mount OK")
        else :
            trace("mount failed")
    if r == 0 :
        trace("image OK")
        dlg_msgbox(_("Image restore succesfully!"))
    else :
        trace("image failed")
        dlg_error(_("Image restore failed! (%(r)s)") % {'r': r})


# proc_inspect:
#
def proc_inspect () :
    while True :
        imglist = list_images()
        if not imglist :
            dlg_msgbox(_("No backup found"))
            return
        devlist = tuple((dev_by_uuid(u, defo=_('<none>')), label_by_uuid(u), u)
                        for u in set(imginfo(i)['uuid'] for i in imglist))
        # select dev
        dev = select_device(devlist=devlist)
        if not dev : return
        while True :
            # select img
            imgname = select_image(uuid=dev[2])
            if not imgname : break
            # go
            iinfo = imginfo(imgname)
            dinfo = devinfo(dev)
            size = human_size(imgsize(imgname))
            d = {'img': imgname, 'size': size, 'devinfo': dinfo,
                 'date': iinfo['date'], 'fname': os.path.join(IMGDIR, imgname)}
            text = (_("IMAGE: %(img)s (%(size)s)\n") +
                    _("DATE:  %(date)s\n") +
                    _("FILE:  %(fname)s\n\n") +
                    _("%(devinfo)s\n\n")) % d
            while True :
                r, out = dlg_yesno(text=text, extra=['--yes-label', _("OK"),
                                                     '--no-label', _("DELETE")])
                if r == 0 :
                    break
                elif r == 1 :
                    warn = text + \
                      _("WARNING: DO YOU REALLY WANT TO DELETE THIS IMAGE ?\n") + \
                      _("(THIS OPERATION IS UNDOABLE)")
                    r, out = dlg_yesno(text=warn, extra=['--defaultno'])
                    if r == 0 :
                        # do it atomically
                        tmpdir = os.path.join(TMPDIR, imgname)
                        if os.path.exists(tmpdir) : shutil.rmtree(tmpdir)
                        os.rename(os.path.join(IMGDIR, imgname), tmpdir)
                        shutil.rmtree(tmpdir)
                        dlg_msgbox(_("Image %(i)s deleted") % {'i': imgname})
                        break
                else :
                    break


# main:
#
def main () :
    try:
        _main()
    except Exception:
        print_exception()
        sys.exit(1)


# _main:
#
def _main () :
    if '--wrapped' in sys.argv[1:] :
        sys.argv.remove('--wrapped')
        real_main()
        return

    # wrapper
    logfile = '/tmp/windump.log'
    flog = open(logfile, 'wb')
    cmd = sys.argv + ['--wrapped']
    proc = subprocess.Popen(cmd, stderr=flog)
    r = proc.wait()
    flog.close()
    screen_reset()
    text = ''
    if r != 0 :
        text += _("Sorry, an error occured (%(r)s).\nMaybe the logs below can help:\n\n" % {'r': r})
    if r != 0 or DEBUG :
        text += open(logfile, 'rt').read()
        dlg_msgbox(text=text)
        trace(_("finished - press enter"))
        input()


# real_main:
#
def real_main () :
    global BLACKLIST, COMPRESS, VOLUME

    # create some dirs
    if os.path.exists(TMPDIR) :
        shutil.rmtree(TMPDIR)
    _mkdir(TMPDIR)
    #_mkdir(PKGVARDIR)
    _mkdir(IMGDIR)

    # read the config
    cfgfile = os.path.join(SYSCONFDIR, PACKAGE + '.conf')
    if os.path.exists(cfgfile) :
        trace("reading config file: '%s'" % cfgfile)
        config = json.load(open(cfgfile, 'rt'))
    else :
        config = {}
    BLACKLIST = config.get('blacklist', ())
    trace("blacklist: %s" % ', '.join(BLACKLIST))
    COMPRESS = int(config.get('compress', '2'))
    VOLUME = int(config.get('volume', str(4*1024)))
        
    # main menu
    text = _("What do you want to do ?")
    menu = (("1", _("Restore a backup")),
            ("2", _("Backup a partition")),
            ("3", _("Inspect existing backups")),
            ("4", _("Quit")))
    while True :
        r, out = dlg_menu(text=text, menu=menu)
        if r != 0 or out == "4" :
            trace("ciao")
            break
        if out == '1' :
            proc_restore()
        elif out == '2' :
            proc_backup()
        elif out == '3' :
            proc_inspect()
        else :
            assert 0, out


# exec
if __name__ == '__main__' :
    main()
