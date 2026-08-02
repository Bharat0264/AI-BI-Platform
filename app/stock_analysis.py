"""Indian market research with strict asset-class resolution."""
import json, math
from datetime import datetime, timezone
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen
import numpy as np

def _get(url):
    with urlopen(Request(url, headers={"User-Agent": "Mozilla/5.0 AI-BI-Platform/1.0"}), timeout=12) as r:
        return json.loads(r.read().decode("utf-8"))

ASSET_TYPES = {
    "stocks": {"EQUITY"},
    "etfs": {"ETF"},
    "mutualfunds": {"MUTUALFUND"},
    "bonds": {"BOND"},
    "futures": {"FUTURE"},
}

# Common market shorthand that differs from the official exchange symbol.
SYMBOL_ALIASES = {"SBI": "SBIN.NS", "STATE BANK OF INDIA": "SBIN.NS"}

def _resolve(query, asset_type):
    kind = asset_type if asset_type in ASSET_TYPES else "stocks"
    entered = query.strip().upper()
    lookup = SYMBOL_ALIASES.get(entered, entered)
    data = _get("https://query1.finance.yahoo.com/v1/finance/search?" + urlencode({"q":lookup,"quotesCount":20,"newsCount":0}))
    matches = [q for q in data.get("quotes",[]) if q.get("quoteType") in ASSET_TYPES[kind] and q.get("exchange") in {"NSI","BSE","NSE","BOM"}]
    if not matches:
        label = {"stocks":"stock","etfs":"ETF","mutualfunds":"mutual fund","bonds":"bond","futures":"futures contract"}[kind]
        raise ValueError(f"No Indian {label} matched '{query}'. Check the selected asset class and symbol.")
    def rank(item):
        symbol = item.get("symbol", "").upper()
        base = symbol.removesuffix(".NS").removesuffix(".BO")
        exact = symbol == lookup or base == lookup
        name = (item.get("longname") or item.get("shortname") or "").upper()
        return (0 if exact else 1, 0 if name == entered else 1, len(name))
    selected = sorted(matches, key=rank)[0]
    return selected["symbol"], selected.get("longname") or selected.get("shortname") or selected["symbol"], kind

def analyze_stock(company, asset_type="stocks"):
    symbol,name,asset_type=_resolve(company.strip(), asset_type)
    result=_get(f"https://query1.finance.yahoo.com/v8/finance/chart/{quote(symbol)}?range=1y&interval=1d")["chart"]["result"][0]
    raw=zip(result.get("timestamp",[]),result["indicators"]["quote"][0].get("close",[]))
    points=[(t,float(c)) for t,c in raw if c is not None and c>0]
    if len(points)<60: raise ValueError("Not enough trading history is available for responsible analysis.")
    prices=np.array([p[1] for p in points]); dates=[datetime.fromtimestamp(p[0],timezone.utc).date().isoformat() for p in points]
    returns=np.diff(np.log(prices)); latest=float(prices[-1]); ma20,ma50,ma200=(float(np.mean(prices[-min(n,len(prices)):])) for n in (20,50,200))
    changes=[latest/prices[-min(n,len(prices))]-1 for n in (22,66,len(prices))]
    vol=float(np.std(returns)*math.sqrt(252)); drift=float(np.clip(np.mean(returns[-126:])*.5,-.0015,.0015)); sigma=max(float(np.std(returns[-126:])),.005)
    rng=np.random.default_rng(42); forecasts=[]
    for label,days in {"1 month":21,"3 months":63,"6 months":126}.items():
        terminal=(latest*np.exp(np.cumsum(rng.normal(drift,sigma,(5000,days)),axis=1)))[:,-1]
        forecasts.append({"horizon":label,"median":round(float(np.median(terminal)),2),"low":round(float(np.percentile(terminal,10)),2),"high":round(float(np.percentile(terminal,90)),2),"positiveProbability":round(float(np.mean(terminal>latest)*100),1)})
    score=int(np.clip(round(50+(12 if latest>ma50 else -12)+(10 if ma50>ma200 else -10)+np.clip(changes[1]*50,-10,10)-np.clip(vol*15,0,12)),0,100))
    meta=result.get("meta",{})
    return {"symbol":symbol,"company":name,"assetType":asset_type,"exchange":meta.get("exchangeName","India"),"currency":meta.get("currency","INR"),"asOf":dates[-1],"price":round(latest,2),"fiftyTwoWeekHigh":round(float(max(prices)),2),"fiftyTwoWeekLow":round(float(min(prices)),2),"returns":{"oneMonth":round(float(changes[0])*100,2),"threeMonths":round(float(changes[1])*100,2),"oneYear":round(float(changes[2])*100,2)},"technicals":{"ma20":round(ma20,2),"ma50":round(ma50,2),"ma200":round(ma200,2),"annualizedVolatility":round(vol*100,2)},"score":score,"stance":"Constructive" if score>=65 else "Cautious" if score>=42 else "High risk","forecasts":forecasts,"chart":{"dates":dates[-180:],"prices":[round(float(v),2) for v in prices[-180:]]},"signals":[f"Price is {'above' if latest>ma50 else 'below'} its 50-day average.",f"The 50-day trend is {'above' if ma50>ma200 else 'below'} the 200-day trend.",f"Annualized historical volatility is {vol*100:.1f}%."],"methodology":"5,000 drift-shrunk Monte Carlo paths; ranges are 10th–90th percentiles, not targets.","disclaimer":"Research information only, not personalized investment advice. Market data may be delayed. Review filings, valuation, governance, taxes, and your risk capacity."}
