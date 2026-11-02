/* A short, plain-language path over the existing analytical APIs. */
window.auraGuide = (() => {
  const byId = id => document.getElementById(id);
  let ready = false, financial = false, navigate = () => {}, file = null;
  const roles = { identifier:'Reference / ID', 'date/time':'Date or time', revenue:'Sales / revenue', profit:'Profit', cost:'Cost', quantity:'Units / quantity', price:'Price', customer:'Customer', product:'Product', category:'Group / category', region:'Place / region', location:'Location', channel:'Channel', 'target/outcome':'Prediction target', 'generic numerical':'Number (meaning not confirmed)', 'generic categorical':'Text / label' };
  const pages = {
    overview:['Start here','Add a file or try the sample to get started.'],
    'data-intelligence':['My data','Preview your file and check the meaning of each column.'],
    dashboard:['Results','See a summary of the data you added.'],
    assistant:['Ask a question','Explore a total, average or comparison in your file.'],
    exports:['Download','Save a copy of your data or a financial report.'],
  };
  const format = value => value !== null && value !== undefined && Number.isFinite(Number(value)) ? Number(value).toLocaleString(undefined,{maximumFractionDigits:2}) : 'Not available';
  function node(tag, text, cls) {
    const element=document.createElement(tag); if (text !== undefined) element.textContent=text; if(cls) element.className=cls; return element;
  }
  function route(page) {
    const label=pages[page] || [[...document.querySelectorAll("nav a[data-page]")].find(link=>link.dataset.page===page)?.textContent || 'More tools','Optional tools for a closer look at your data.'];
    byId('currentPageTitle').textContent=label[0];byId('currentPageHint').textContent=label[1];
    byId('dashboardFilters').hidden=!(ready && financial && page==='dashboard');
    const active=[...document.querySelectorAll('nav a[data-page]')].find(link=>link.dataset.page===page);
    if(active?.closest('#advancedNavigation'))byId('advancedNavigation').open=true;
  }
  function update(payload) {
    file=payload;ready=Number(payload.rows)>0;financial=ready && payload.dashboard_mode!=='general';
    document.body.classList.toggle('has-data',ready);
    document.querySelectorAll('[data-needs-data]').forEach(element=>element.hidden=!ready);
    document.querySelectorAll('[data-empty-state]').forEach(element=>element.hidden=ready);
    byId('uploadNextSteps').hidden=!ready;
    byId('readyFileName').textContent=ready ? payload.source : '';
    byId('readyFileSummary').textContent=ready ? `${format(payload.rows)} rows loaded. Your original file stays unchanged. Choose what to do next.` : '';
    byId('executiveSummary').parentElement.hidden=!financial;
    byId('generalResults').hidden=!ready || financial;
    byId('financialResults').hidden=!financial;
    byId('resultsExplanation').textContent=financial ? 'Your financial overview. These charts use the revenue, profit and dates in your file.' : 'This file is ready for general analysis. Financial charts need revenue, profit and dates; you can still explore its numbers below.';
    byId('reportAvailability').textContent=financial ? 'Create a PDF of the available financial overview and current result filters.' : 'A financial PDF report requires revenue, profit and date columns. You can download your data as CSV instead.';
    byId('generateReportLink').setAttribute('aria-disabled',String(!financial));
    byId('simpleNumberSummary').replaceChildren();
    byId('questionExamples').replaceChildren();
    if(ready) {
      byId('questionExamples').append(node('p','Checking your columns for example questions…','muted'));
      const facts=[['Rows',payload.rows],['Columns',payload.quality?.columns],['Empty cells',payload.quality?.missingCells],['Repeated rows',payload.quality?.duplicateRows]];
      byId('fileFactCards').replaceChildren(...facts.map(([label,value])=>{
        const card=node('article',undefined,'card');card.append(node('span',label,'metric-label'),node('strong',format(value),'metric-value'));return card;
      }));
      const preview=byId('previewTable');byId('simpleDataPreview').innerHTML=preview.innerHTML;
    }
    route(location.hash.slice(1) || 'overview');
  }
  function inspect(data) {
    if(!ready)return;
    const fields=data.semantic_schema || [], profile=data.profile || {};
    const measureRoles=new Set(['revenue','profit','cost','quantity']);
    const total=fields.find(field=>measureRoles.has(field.semantic_role));
    const numeric=fields.find(field=>['revenue','profit','cost','quantity','price','generic numerical'].includes(field.semantic_role));
    const group=fields.find(field=>['region','category'].includes(field.semantic_role));
    const examples=[];
    if(total)examples.push([`Total ${total.column}`,`What is ${total.column}?`]);
    if(numeric)examples.push([`Average ${numeric.column}`,`What is average ${numeric.column}?`]);
    if(total && group)examples.push([`${total.column} by ${group.column}`,`Show ${total.column} by ${group.column}`]);
    byId('questionExamples').replaceChildren(node('p',examples.length?'Try a question about your file:':'No suitable number column was found. Check column meanings in My data first.','muted'));
    for(const [label,question] of examples) {
      const button=node('button',label,'example-question');button.type='button';button.setAttribute('data-analyst-action','');
      button.addEventListener('click',()=>{byId('question').value=question;byId('question').dispatchEvent(new Event('input',{bubbles:true}));byId('question').focus();});
      byId('questionExamples').append(button);
    }
    const table=byId('simpleNumberSummary');table.replaceChildren();
    const numericFields=fields.filter(field=>['revenue','profit','cost','quantity','price','generic numerical'].includes(field.semantic_role) && profile.column_profile?.[field.column]?.statistics);
    if(!numericFields.length) {table.append(node('caption','No number-column summary is available yet. Review the column meanings in My data.'));return;}
    const head=node('thead'), row=node('tr');for(const label of ['Column','Smallest value','Largest value','Average'])row.append(node('th',label));head.append(row);table.append(head);
    const body=node('tbody');
    for(const field of numericFields.slice(0,12)) {
      const stats=profile.column_profile[field.column].statistics, row=node('tr');
      for(const value of [field.column,format(stats.min),format(stats.max),format(stats.mean)])row.append(node('td',value));body.append(row);
    }
    table.append(body);
  }
  function busy(value, source='upload') {
    byId('uploadForm').setAttribute('aria-busy',String(value));
    byId('datasetFile').disabled=value;byId('demoButton').disabled=value;
    byId('analyzeCsvButton').disabled=value || !byId('datasetFile').files.length;
    byId('analyzeCsvButton').textContent=value && source==='upload'?'Reading your file…':'Upload file';
    byId('demoButton').textContent=value && source==='sample'?'Loading sample…':'Try sample data';
  }
  function configure(options) {
    navigate=options.navigate;
    document.addEventListener('click',event=>{
      const action=event.target.closest('[data-go-page]');if(!action)return;
      event.preventDefault();navigate(action.dataset.goPage,{updateHash:true});
      if(action.dataset.goPage==='overview')byId('datasetFile').focus();
    });
    byId('openQuickHelp').addEventListener('click',()=>byId('quickHelp').showModal());
    byId('closeQuickHelp').addEventListener('click',()=>byId('quickHelp').close());
    byId('datasetFile').addEventListener('change',()=>busy(false));
  }
  return {configure,update,inspect,route,busy,roleLabel:role=>roles[role] || role,get ready(){return ready;},get financial(){return financial;}};
})();
