(function(){
  'use strict';
  const path=location.pathname,base=path==='/erp'||path.startsWith('/erp/')?'/erp':'';
  const url=value=>typeof value==='string'&&value.startsWith('/')&&!value.startsWith(base+'/')?base+value:value;
  window.appUrl=window.appUrl||url;
  const originalFetch=window.fetch.bind(window);let redirecting=false;
  window.fetch=async function(resource,options){
    const response=await originalFetch(url(resource),options);
    const requestUrl=typeof resource==='string'?resource:(resource?.url||'');
    const isLoginRequest=requestUrl.includes('/auth/login');
    if((response.status===401||response.status===410)&&!isLoginRequest&&!redirecting){
      redirecting=true;['token','role','username'].forEach(key=>localStorage.removeItem(key));
      sessionStorage.setItem('authMessage','Your session expired. Please sign in again.');
      location.replace(url('/login'));
    }
    return response;
  };
  if('serviceWorker'in navigator)addEventListener('load',()=>navigator.serviceWorker.register(url('/sw.js'),{scope:(base||'')+'/'}).catch(()=>{}),{once:true});
  function enhance(){let favicon=document.querySelector('link[rel~="icon"]');if(!favicon){favicon=document.createElement('link');favicon.rel='icon';document.head.appendChild(favicon)}favicon.type='image/png';favicon.sizes='192x192';favicon.href=url('/static/icons/icon-192.png');document.querySelectorAll('table').forEach(table=>{if(table.parentElement?.classList.contains('app-table-scroll'))return;const wrap=document.createElement('div');wrap.className='app-table-scroll';wrap.tabIndex=0;wrap.setAttribute('role','region');wrap.setAttribute('aria-label','Scrollable table');table.before(wrap);wrap.appendChild(table)});document.querySelectorAll('img:not([alt])').forEach(img=>img.alt='');document.querySelectorAll('button:not([type])').forEach(button=>button.type='button');if(!localStorage.getItem('token')||document.querySelector('.app-mobile-nav'))return;const links=[['Home','/home'],['Schemes','/dashboard'],['Attendance','/attendance']],nav=document.createElement('nav');nav.className='app-mobile-nav';nav.setAttribute('aria-label','Mobile navigation');nav.innerHTML=links.map(([label,href])=>'<a href="'+url(href)+'"'+(path===base+href||path===base+href+'.html'?' aria-current="page"':'')+'>'+label+'</a>').join('');document.body.appendChild(nav);const banner=document.createElement('div');banner.className='app-offline-banner';banner.textContent='Offline — changes will sync when connected';banner.hidden=navigator.onLine;document.body.appendChild(banner);addEventListener('online',()=>banner.hidden=true);addEventListener('offline',()=>banner.hidden=false)}
  if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',enhance,{once:true});else enhance();
  document.addEventListener('keydown',event=>{if(event.key==='Escape')document.querySelectorAll('.modal.show,.record-modal.show').forEach(modal=>modal.querySelector('[id=cancel],.record-close,[data-close]')?.click())});
})();
(function(){const role=localStorage.getItem('role')||'',token=localStorage.getItem('token');if(!token)return;const base=location.pathname==='/erp'||location.pathname.startsWith('/erp/')?'/erp':'',route=location.pathname.slice(base.length).replace(/\.html$/,'')||'/';const unrestricted=['Admin','Owner','HR','MISExecutive','Accounts'],schemeRoles=[...unrestricted,'CategoryManager','BrandManager'],publicRoutes=['/','/login','/signup','/forgot-password','/reset-password','/privacy','/offline'],basicRoutes=['/home','/attendance'];if(!publicRoutes.includes(route)&&!basicRoutes.includes(route)&&!(route==='/dashboard'&&schemeRoles.includes(role))&&!unrestricted.includes(role)){location.replace((base||'')+'/home');return}function trimMobileNav(){if(['BrandPartner','SupportingStaff'].includes(role))document.querySelector('.app-mobile-nav a[href$="/dashboard"]')?.remove()}if(document.readyState==='loading')document.addEventListener('DOMContentLoaded',trimMobileNav,{once:true});else trimMobileNav()})();
