import hashlib,hmac,re
from datetime import datetime,timezone
from urllib.parse import quote
from quart import request
from app.config import Config
from .xml import error

def _canonical_query():
    vals=[]
    for k,v in request.args.items(multi=True):
        if k != 'X-Amz-Signature': vals.append((quote(k,safe='-_.~'),quote(v,safe='-_.~')))
    return '&'.join(f'{k}={v}' for k,v in sorted(vals))
def _canonical_headers(names):
    return ''.join(f'{n}:{" ".join(request.headers.get(n," ").strip().split())}\n' for n in names)
def validate():
    return validate_with_error()[0]

def validate_with_error():
    auth=request.headers.get("Authorization","")
    q=request.args
    if auth.startswith("AWS4-HMAC-SHA256 "):
        m=re.match(r'AWS4-HMAC-SHA256 Credential=([^/]+)/([^,]+), SignedHeaders=([^,]+), Signature=([0-9a-f]+)',auth)
        if not m: return False, 'AccessDenied'
        access=m.group(1); scope=m.group(2).split("/"); signed=m.group(3).split(";"); sig=m.group(4); amzdate=request.headers.get("x-amz-date")
        if len(scope) != 4: return False, 'AccessDenied'
        date,region,service,term=scope
        if access!=Config().S3_ACCESS_KEY_ID: return False, 'InvalidAccessKeyId'
        if region!=Config().S3_REGION or service!=Config().S3_SERVICE or not amzdate: return False, 'SignatureDoesNotMatch'
        try:
            skew=abs((datetime.now(timezone.utc)-datetime.strptime(amzdate,'%Y%m%dT%H%M%SZ').replace(tzinfo=timezone.utc)).total_seconds())
            if skew>900: return False, 'RequestTimeTooSkewed'
        except ValueError: return False, 'AccessDenied'
        payload=request.headers.get("x-amz-content-sha256","UNSIGNED-PAYLOAD")
        canonical='\n'.join([request.method,quote(request.path,safe='/-_.~'),_canonical_query(),_canonical_headers(signed),'', ';'.join(signed),payload])
        if _signature(canonical,date,region,service,amzdate,sig): return True, None
        try:
            from botocore.awsrequest import AWSRequest
            from botocore.auth import SigV4Auth
            from botocore.credentials import Credentials
            hdr={n: request.headers.get(n, '') for n in signed}
            r=AWSRequest(method=request.method,url=request.url,headers=hdr); r.context['timestamp']=amzdate
            a=SigV4Auth(Credentials(Config().S3_ACCESS_KEY_ID,Config().S3_SECRET_ACCESS_KEY),service,region)
            return hmac.compare_digest(a.signature(a.string_to_sign(r,a.canonical_request(r)),r),sig), 'SignatureDoesNotMatch'
        except Exception: return False, 'SignatureDoesNotMatch'
    if q.get("X-Amz-Algorithm")=="AWS4-HMAC-SHA256":
        cred=q.get("X-Amz-Credential","").split("/"); signed=q.get("X-Amz-SignedHeaders","").split(";"); sig=q.get("X-Amz-Signature","")
        if len(cred)!=5: return False, 'AccessDenied'
        if cred[0]!=Config().S3_ACCESS_KEY_ID: return False, 'InvalidAccessKeyId'
        if q.get("X-Amz-Expires","0").isdigit() is False: return False, 'AccessDenied'
        try:
            dt=datetime.strptime(q.get("X-Amz-Date"),"%Y%m%dT%H%M%SZ").replace(tzinfo=timezone.utc); expires=int(q["X-Amz-Expires"])
            if expires < 1 or expires > 604800: return False, 'AccessDenied'
            age=(datetime.now(timezone.utc)-dt).total_seconds()
            if age < -900: return False, 'RequestTimeTooSkewed'
            if age > expires: return False, 'AccessDenied'
        except (ValueError,TypeError): return False, 'AccessDenied'
        payload="UNSIGNED-PAYLOAD"; canonical='\n'.join([request.method,quote(request.path,safe='/-_.~'),_canonical_query(),_canonical_headers(signed),'',';'.join(signed),payload])
        return (_signature(canonical,cred[1],cred[2],cred[3],q["X-Amz-Date"],sig), 'SignatureDoesNotMatch')
    return False, 'AccessDenied'
def _signature(canonical,date,region,service,amzdate,provided):
    secret=Config().S3_SECRET_ACCESS_KEY; kDate=hmac.new(("AWS4"+secret).encode(),date.encode(),hashlib.sha256).digest(); kRegion=hmac.new(kDate,region.encode(),hashlib.sha256).digest(); kService=hmac.new(kRegion,service.encode(),hashlib.sha256).digest(); key=hmac.new(kService,b"aws4_request",hashlib.sha256).digest()
    scope=f"{date}/{region}/{service}/aws4_request"; hashed=hashlib.sha256(canonical.encode()).hexdigest(); string=f"AWS4-HMAC-SHA256\n{amzdate}\n{scope}\n{hashed}"; expected=hmac.new(key,string.encode(),hashlib.sha256).hexdigest()
    if hmac.compare_digest(expected,provided): return True
    # Match botocore's canonicalization for clients that normalize header casing differently.
    try:
        from botocore.awsrequest import AWSRequest
        from botocore.auth import SigV4Auth
        from botocore.credentials import Credentials
        hdr={n: request.headers.get(n, '') for n in request.headers if n.lower() in ('host', 'x-amz-date', 'x-amz-content-sha256', 'content-type')}
        r=AWSRequest(method=request.method, url=request.url, headers=hdr); r.context['timestamp']=amzdate
        a=SigV4Auth(Credentials(Config().S3_ACCESS_KEY_ID, Config().S3_SECRET_ACCESS_KEY), service, region)
        return hmac.compare_digest(a.signature(a.string_to_sign(r, a.canonical_request(r)), r), provided)
    except Exception: return False
