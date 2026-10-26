// Read and click the actual captured client. Findings never count as feature passes.
const fs=require('node:fs');
const path=require('node:path');
module.exports=async({page,base,output})=>{
  const probes=[
    ['profile-name','settings',()=>page.getByRole('button',{name:'Edit',exact:true}).nth(0)],
    ['profile-cashtag','settings',()=>page.getByRole('button',{name:'Edit',exact:true}).nth(1)],
    ['profile-address','settings',()=>page.getByRole('button',{name:'Add',exact:true}).nth(0)],
    ['profile-email','settings',()=>page.getByRole('button',{name:'Add',exact:true}).nth(1)],
    ['profile-phone','settings',()=>page.getByRole('button',{name:'Add',exact:true}).nth(2)],
    ['bank-replace','settings',()=>page.getByRole('button',{name:'Replace debit card',exact:true})],
    ['bank-remove','settings',()=>page.getByRole('button',{name:'Remove debit card',exact:true})],
    ['bank-link','settings',()=>page.getByRole('button',{name:'Link bank',exact:true})],
    ['security-pin','settings',()=>page.getByRole('button',{name:'Change Cash PIN',exact:true})],
    ['security-lock','settings',()=>page.getByRole('checkbox').nth(0)],
    ['security-passkey','settings',()=>page.getByRole('button',{name:'Add passkey',exact:true})],
    ['security-tax-password','settings',()=>page.getByRole('button',{name:'Create password',exact:true})],
    ['privacy-public','settings',()=>page.getByRole('checkbox',{name:/^Allow others to find me/})],
    ['privacy-requests','settings',()=>page.getByRole('checkbox',{name:'Incoming requests',exact:true})],
    ['notifications-transactions','settings',()=>page.getByText('Transactions',{exact:true})],
    ['appearance-light','settings',()=>page.getByText('Light',{exact:true})],
    ['appearance-dark','settings',()=>page.getByText('Dark',{exact:true})],
    ['privacy-download','settings',()=>page.getByRole('button',{name:'Download your info',exact:true})],
    ['privacy-close','settings',()=>page.getByRole('button',{name:'Close Cashlarp account',exact:true})],
    ['savings-goal','savings',()=>page.getByText('Set goal',{exact:true})],
    ['savings-roundups','savings',()=>page.getByText('Round Ups',{exact:true})],
    ['card-lock','card',()=>page.getByRole('checkbox',{name:'Lock card',exact:true})],
    ['card-replacement','card',()=>page.getByText('Order a replacement card',{exact:true})],
    ['card-design','card',()=>page.getByText('Design a new card',{exact:true})],
    ['money-add','money',()=>page.getByRole('button',{name:'Add money',exact:true})],
    ['money-withdraw','money',()=>page.getByRole('button',{name:'Withdraw',exact:true})],
    ['bitcoin-buy','bitcoin',()=>page.getByRole('button',{name:'Buy',exact:true})],
    ['bitcoin-sell','bitcoin',()=>page.getByRole('button',{name:'Sell',exact:true})],
    ['activity-download','activity',()=>page.getByRole('button',{name:'Download',exact:true})],
  ];
  const findings=[];
  for(const [name,route,control] of probes){
    const finding={name,route,requests:[],downloads:[]};
    const response=async r=>{
      const url=new URL(r.url());if(url.origin!==base)return;
      const request=r.request();if(request.method()!=='POST')return;
      finding.requests.push({path:url.pathname,status:r.status(),body:request.postData(),response:r.status()>=400?await r.text().catch(()=>null):undefined});
    };
    const download=d=>finding.downloads.push(d.suggestedFilename());
    try{
      await page.goto(base+'/account/'+route);
      await page.locator('#root a').first().waitFor();
      await page.waitForLoadState('networkidle');
      const before=await page.locator('body').innerText();
      page.on('response',response);page.on('download',download);
      await control().first().click({timeout:4000});
      await page.waitForTimeout(800);
      await page.waitForLoadState('networkidle',{timeout:4000}).catch(()=>{});
      finding.url=page.url();
      const after=await page.locator('body').innerText();
      finding.screen=after.slice(-10000);
      finding.dialogs=await page.getByRole('dialog').allTextContents();
      finding.inputs=await page.locator('input:visible,select:visible,button:visible,a[role=button]:visible').evaluateAll(nodes=>nodes.map(n=>({tag:n.tagName,type:n.getAttribute('type'),label:n.getAttribute('aria-label'),name:n.getAttribute('name'),placeholder:n.getAttribute('placeholder'),text:n.textContent.trim().slice(0,100)})));
      finding.status=finding.requests.some(r=>r.status>=400)?'rpc-error':finding.downloads.length?'download':before!==after?'screen-changed':'no-visible-change';
    }catch(error){finding.status='interaction-error';finding.error=error.message;}
    finally{
      page.off('response',response);page.off('download',download);
      await page.screenshot({path:path.join(output,'audit-'+name+'.png'),fullPage:true}).catch(()=>{});
      findings.push(finding);
      fs.writeFileSync(path.join(output,'interaction-audit.json'),JSON.stringify(findings,null,2)+'\n');
    }
  }
  // Restore the original appearance setting after the visual probes.
  await page.goto(base+'/account/settings');
  await page.getByText('Auto',{exact:true}).click();
  console.log('Native interaction audit: '+findings.map(f=>f.name+'='+f.status).join(', '));
  return findings;
};
