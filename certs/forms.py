import dateutil.parser

from django import forms

from .models import CACertificate, Certificate

from OpenSSL import crypto
from certs.certgen.certgen import (
    createKeyPair,
    createCertRequest,
    createCertificate,
)

MAX_LENGTH = 1000
YEARS_MAX = 100

"""
TODO: Make MAX_LENGTH and YEARS_MAX changeable through config page
"""


class CertificateForm(forms.Form):
    countryName = forms.CharField(label='Country Name (2 letter code) [AU]',
                                  max_length=2,
                                  required=False)
    stateOrProvinceName = forms.CharField(label='State or Province Name (full name) [Some-State]',
                                          max_length=MAX_LENGTH,
                                          required=False)
    localityName = forms.CharField(label='Locality Name (eg, city) []',
                                   max_length=MAX_LENGTH,
                                   required=False)
    organizationName = forms.CharField(label='Organization Name (eg, company) [Internet Widgits Pty Ltd]',
                                       max_length=MAX_LENGTH,
                                       required=False)
    organizationalUnitName = forms.CharField(label='Organizational Unit Name (eg, section) []',
                                             max_length=MAX_LENGTH,
                                             required=False)
    commonName = forms.CharField(label='Common Name (e.g. server FQDN or YOUR name) []',
                                 max_length=MAX_LENGTH,
                                 required=False)
    emailAddress = forms.CharField(label='Email Address []',
                                   max_length=MAX_LENGTH,
                                   required=False)

    def create_certificate(self, form):
        cert_data = {}
        form_data = {}
        cert_data['C'] = form['country_name']
        cert_data['ST'] = form['state_name']
        cert_data['L'] = form['locality_name']
        cert_data['O'] = form['organization_name']
        cert_data['OU'] = form['organizational_unit_name']
        cert_data['CN'] = form['common_name']
        cert_data['emailAddress'] = form['email_address']
        for key in form:
            if form[key] != '':
                form_data[key] = str(form[key])

        for key in cert_data.keys():
            if cert_data[key] != '':
                cert_data[key] = str(cert_data[key])
            else:
                cert_data.pop(key)

        """
        Create a certificate request.

        Arguments: pkey   - The key to associate with the request
                   digest - Digestion method to use for signing, default is sha256
                   **name - The name of the subject of the request, possible
                            arguments are:
                              C     - Country name
                              ST    - State or province name
                              L     - Locality name (eg, city)
                              O     - Organization name
                              OU    - Organizational unit name
                              CN    - Common name
                              emailAddress - E-mail address
        """
        pkey = createKeyPair(crypto.TYPE_RSA, 2048)

        if len(cert_data) == 0:
            req = createCertRequest(pkey)
        else:
            req = createCertRequest(pkey, **form_data)

        # Certificates are valid for five years.
        ca_obj = CACertificate.objects.filter(id=1).get()
        cakey = crypto.load_privatekey(crypto.FILETYPE_PEM, ca_obj.key)
        cacert = crypto.load_certificate(crypto.FILETYPE_PEM, ca_obj.certificate)
        cert = createCertificate(req, (cacert, cakey), 1, (0, 60 * 60 * 24 * 365 * 5))

        cert = crypto.dump_certificate(crypto.FILETYPE_PEM, cert).decode('utf-8')
        key = crypto.dump_privatekey(crypto.FILETYPE_PEM, pkey).decode('utf-8')
        sign_req = crypto.dump_certificate_request(crypto.FILETYPE_PEM, req).decode('utf-8')
        Certificate.create_certificate(cert, key, sign_req, ca_certificate=ca_obj, **form_data)

    def create_ca_certificate(self, form):
        for key in form.keys():
            temp_str = form[key]
            form[key] = temp_str.strip()
            if form[key] == '':
                form.pop(key)

        cakey = createKeyPair(crypto.TYPE_RSA, 2048)
        # if len(form_data) == 0:
        #     careq = createCertRequest(cakey)
        # else:
        #     careq = createCertRequest(cakey, **cert_data)
        careq = createCertRequest(cakey, **form)
        # CA certificate is valid for five years.
        last_cert = CACertificate.objects.latest('id')
        cacert = createCertificate(careq, (careq, cakey), last_cert+1, (0, 60 * 60 * 24 * 365 * YEARS_MAX))
        cert = crypto.dump_certificate(crypto.FILETYPE_PEM, cacert).decode('utf-8')
        key = crypto.dump_privatekey(crypto.FILETYPE_PEM, cakey).decode('utf-8')
        sign_req = crypto.dump_certificate_request(crypto.FILETYPE_PEM, careq).decode('utf-8')
        not_before_date = dateutil.parser.parse(cacert.get_notBefore())
        not_after_date = dateutil.parser.parse(cacert.get_notAfter())

        CACertificate.create_certificate(cert=cert,
                                         key=key,
                                         signingRequest=sign_req,
                                         notBeforeDate=not_before_date,
                                         notAfterDate=not_after_date,
                                         **form)


