"""Daily refresh worker. Bootstrap historical data with the CLI BEFORE enabling this.
Earthdata extraction is deliberately not advertised as an automatic production pipeline.
"""
import logging, time, subprocess, sys
logging.basicConfig(level=logging.INFO)
if __name__=='__main__':
    while True:
        result=subprocess.run([sys.executable,'-m','app.ingestion','power'],check=False)
        logging.info('POWER daily refresh exited %s',result.returncode)
        time.sleep(24*60*60)
