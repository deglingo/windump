#

LANGLIST = fr

PACKAGE = windump

prefix = /usr/local
sbindir = $(prefix)/sbin
sysconfdir = $(prefix)/etc
sharedir = $(prefix)/share
localedir = $(sharedir)/locale
vardir = /var/local
pkgvardir = $(vardir)/$(PACKAGE)

POFILES = $(LANGLIST:%=%/$(PACKAGE).po)
MOFILES = $(LANGLIST:%=%/$(PACKAGE).mo)

DESKTOP_LAUNCHER = $(PACKAGE).desktop

.PHONY: all install install-icon

all: $(PACKAGE) $(POFILES) $(MOFILES)

$(PACKAGE): $(PACKAGE).py conf.sed
	sed -f conf.sed <$< >$@.tmp
	mv -f $@.tmp $@

conf.sed: Makefile
	(	echo "s,@PACKAGE@,$(PACKAGE),g"; \
		echo "s,@SBINDIR@,$(sbindir),g"; \
		echo "s,@SYSCONFDIR@,$(sysconfdir),g"; \
		echo "s,@LOCALEDIR@,$(localedir),g"; \
		echo "s,@PKGVARDIR@,$(pkgvardir),g"; \
	) >$@.tmp
	mv -f $@.tmp $@

%.mo: %.po
	lang=`dirname "$@"`; \
	msgfmt -o$@.tmp $<
	mv -f $@.tmp $@

%.po: %.pot
	lang=`dirname "$@"`; \
	if test -f $@; then \
		cp -vf $@ $@.precious; \
		msgmerge -U $@ $< && rm -f $@.precious || { \
			r=$?; \
			mv -f $@.precious $@; \
			echo "ERROR: msgmerge failed ($$r)" >&2; \
			exit $r; }; \
	else \
		( echo "# -*- encoding: utf-8 -*-"; cat $<; ) >$@.tmp \
			&& mv -f $@.tmp $@; \
	fi

%.pot: windump.py
	lang=`dirname "$@"`; \
	test -d "$$lang" || mkdir -vp "$$lang"
	rm -f $@ $@.tmp
	xgettext -F --package-name=$(PACKAGE) -d$(PACKAGE) -Lpython -o$@.tmp $<
	mv -f $@.tmp $@

install: all
	test -d "$(sbindir)" || mkdir -vp "$(sbindir)"
	test -d "$(pkgvardir)" || mkdir -vp "$(pkgvardir)"
	install -m755 -T "$(PACKAGE)" "$(sbindir)/$(PACKAGE)"
	test -f "$(sysconfdir)/$(PACKAGE).conf" || \
		install -m644 -T "$(PACKAGE).conf.default" "$(sysconfdir)/$(PACKAGE).conf"
	for lang in $(LANGLIST); do \
		modir="$(localedir)/$$lang/LC_MESSAGES"; \
		test -d "$$modir" || mkdir -vp "$$modir"; \
		install -m644 -T "$$lang/$(PACKAGE).mo" "$$modir/$(PACKAGE).mo"; \
	done

# usage: `sudo make install-icon USER=<USERNAME>'
install-icon: $(DESKTOP_LAUNCHER)
	test x"$(USER)" != x || { \
		echo "E: USER not set" >&2; \
		exit 1; }
	desk="`su $(USER) -c 'xdg-user-dir DESKTOP'`"; \
	test -d "$$desk" || { \
		echo "E: $(USER)'s desktop is not a directory: '$$desk'" >&2; \
		exit 1; }; \
	echo "** Installing desktop icon for '$(USER)' in '$$desk' **"; \
	install -m755 -t "$$desk" "$(DESKTOP_LAUNCHER)"

%.desktop: %.desktop.in conf.sed
	sed -f conf.sed <$< >$@.tmp
	mv -f $@.tmp $@
