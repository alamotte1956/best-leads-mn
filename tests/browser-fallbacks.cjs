const vm=require('node:vm');const fs=require('node:fs');const code=fs.readFileSync('static/js/request-experience.js','utf8');
for(const scenario of ['no-fetch','no-formdata-iteration','no-validation']){
 const form={querySelector(){return {reportValidity:scenario==='no-validation'?undefined:function(){}}},querySelectorAll(){throw Error('Enhanced mode must not initialize')}};
 function FormData(){}; if(scenario!=='no-formdata-iteration')FormData.prototype.forEach=function(){};
 vm.runInNewContext(code,{document:{getElementById(){return form}},window:{fetch:scenario==='no-fetch'?undefined:function(){},FormData},Array});
}
console.log('Three feature-fallback checks passed; native form remains available.');
