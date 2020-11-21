## Generate self signed certificate

### Use openssl

#### configure file

Save this file as `cert.cnf`. [source](https://medium.com/@antelle/how-to-generate-a-self-signed-ssl-certificate-for-an-ip-address-f0dd8dddf754)

```ini
# cert.cnf
[req]
default_bits  = 2048
distinguished_name = req_distinguished_name
req_extensions = req_ext
x509_extensions = v3_req
prompt = no

[req_distinguished_name]
countryName = XX
stateOrProvinceName = N/A
localityName = N/A
organizationName = Self-signed certificate
commonName = 120.0.0.1: Self-signed certificate

[req_ext]
subjectAltName = @alt_names

[v3_req]
subjectAltName = @alt_names

[alt_names]
IP.1 = 127.0.0.1
DNS.1 = localhost
DNS.2 = localhost.localdomain
```

#### Generate

```shell script
openssl req -nodes -new -x509 -newkey rsa:4096 -keyout cert.key -out cert.pem -config cert.cnf
# Optional:
# openssl x509 -outform der -in cert.pem -out cert.crt
```

Insert this self signed certificate to your system