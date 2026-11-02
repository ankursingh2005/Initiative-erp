// Infer only an unambiguous month/year; never substitute today's month.
function incentiveMonthFromFilename(filename){
 const text=String(filename||'').replace(/[_-]/g,' ').toLowerCase();
 const years=[...new Set(text.match(/\b(?:19|20)\d{2}\b/g)||[])];
 if(years.length!==1)return '';
 const names=['jan(?:uary)?','feb(?:ruary)?','mar(?:ch)?','apr(?:il)?','may','jun(?:e)?','jul(?:y)?','aug(?:ust)?','sep(?:t(?:ember)?)?','oct(?:ober)?','nov(?:ember)?','dec(?:ember)?'];
 const months=names.map((name,i)=>new RegExp('\\b'+name+'\\b','i').test(text)?i+1:null).filter(Boolean);
 if(months.length===1)return years[0]+'-'+String(months[0]).padStart(2,'0');
 if(months.length>1)return '';
 const numeric=text.match(/\b((?:19|20)\d{2})\s+(0?[1-9]|1[0-2])\b/)||text.match(/\b(0?[1-9]|1[0-2])\s+((?:19|20)\d{2})\b/);
 if(!numeric)return '';
 const year=numeric[1].length===4?numeric[1]:numeric[2],month=numeric[1].length===4?numeric[2]:numeric[1];
 return year+'-'+month.padStart(2,'0');
}
