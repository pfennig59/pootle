#!/usr/bin/env python
# -*- coding: utf-8 -*-
#
# Copyright 2013-2014 Evernote Corporation
#
# This file is part of Pootle.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 2 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program; if not, see <http://www.gnu.org/licenses/>.

import base64
import re
import time

from pyDes import triple_des, ECB

from django.conf import settings
from django.contrib import auth
from django.contrib.auth.decorators import login_required
from django.contrib.auth.forms import AuthenticationForm
from django.core.urlresolvers import reverse
from django.shortcuts import render_to_response
from django.template import RequestContext
from django.utils.http import urlencode
from django.views.decorators.cache import never_cache

from pootle_misc.baseurl import redirect
from pootle_profile.views import redirect_after_login

from .models import EvernoteAccount


def get_cookie_dict(request):
    cookie = request.COOKIES.get(getattr(settings, 'SSO_COOKIE', ''))

    if cookie:
        data = base64.b64decode(cookie)

        des3 = triple_des(getattr(settings, 'SSO_SECRET_KEY', ''), ECB)
        match = re.match(r'i=(?P<id>[0-9]+),'
                         r'u=(?P<name>[^,]+),'
                         r'e=(?P<email>[^,]+),'
                         r'x=(?P<expired>[0-9]+)',
                         des3.decrypt(data))

        if match:
            data = match.groupdict()
            if time.time() < data['expired']:
                return data

    return None


def sso_return_view(request, redirect_to='', create=0):
    redirect_to = '/%s' % redirect_to.lstrip('/')

    data = get_cookie_dict(request)
    if data:
        ea = EvernoteAccount.objects.filter(**{'evernote_id': data['id']})

        if len(ea) == 0:
            if not create:
                return redirect('/accounts/evernote/login/link?%s' %
                        urlencode({auth.REDIRECT_FIELD_NAME: redirect_to}))

            ea = EvernoteAccount(
                evernote_id=data['id'],
                email=data['email'],
                name=data['name']
            )

            if request.user.is_authenticated():
                ea.user = request.user
            else:
                # create new Pootle user
                user = auth.authenticate(**{'evernote_account': ea})
                auth.login(request, user)

            ea.save()

        else:
            ea = ea[0]

            if request.user.is_authenticated():
                if request.user.id != ea.user.id:
                    # it's not possible to link account with another user_id
                    # TODO show error message
                    return redirect(redirect_to)
            else:
                user = auth.authenticate(**{'evernote_account': ea})
                auth.login(request, user)

        return redirect_after_login(request)

    return redirect('/accounts/evernote/login/?%s' %
                    urlencode({auth.REDIRECT_FIELD_NAME: redirect_to}))


def evernote_login(request, create=0):
    redirect_to = request.REQUEST.get(auth.REDIRECT_FIELD_NAME, '')

    script_name = (settings.SCRIPT_NAME and "%s/" %
                   settings.SCRIPT_NAME.rstrip('/').lstrip('/') or '')
    server_alias = getattr(settings, 'EVERNOTE_LOGIN_REDIRECT_SERVER_ALIAS' ,'')

    if not request.user.is_authenticated():
        if create:
            return sso_return_view(request, redirect_to, create)

        return redirect(
            getattr(settings, 'EVERNOTE_LOGIN_URL', '') +
            '%s/%saccounts/evernote/return/%s' %
            (server_alias, script_name, redirect_to.lstrip('/'))
        )

    if not hasattr(request.user, 'evernote_account'):
        return redirect(
            getattr(settings, 'EVERNOTE_LOGIN_URL', '') +
            '%s/%saccounts/evernote/create/return/%s' %
            (server_alias, script_name, redirect_to.lstrip('/'))
        )

    return redirect_after_login(request)


def evernote_login_link(request):
    """Logs the user in."""
    if request.user.is_authenticated():
        return redirect_after_login(request)
    else:
        if request.POST:
            form = AuthenticationForm(request, data=request.POST)

            # Do login here
            if form.is_valid():
                auth.login(request, form.get_user())

                data = get_cookie_dict(request)
                if not data:
                    return evernote_login(request, 1)

                # FIXME: shouldn't `get_or_create()` be enough?
                ea = EvernoteAccount.objects.filter(**{'evernote_id': data['id']})
                if len(ea) == 0:
                    ea = EvernoteAccount(
                        evernote_id=data['id'],
                        email=data['email'],
                        name=data['name']
                    )
                    ea.user = request.user
                    ea.save()

                return redirect_after_login(request)
        else:
            form = AuthenticationForm(request)

        context = {
            'form': form,
            'next': request.REQUEST.get(auth.REDIRECT_FIELD_NAME, ''),
        }

        return render_to_response("auth/link_with_evernote.html", context,
                                  context_instance=RequestContext(request))


@login_required
@never_cache
def evernote_account_info(request, context={}):
    return render_to_response('profiles/settings/evernote_account.html',
                              context, context_instance=RequestContext(request))


@login_required
def evernote_account_disconnect(request):
    if hasattr(request.user, 'evernote_account'):
        ea = request.user.evernote_account
        if not ea.user_autocreated:
            ea.delete()

    return redirect('/accounts/evernote/link/')