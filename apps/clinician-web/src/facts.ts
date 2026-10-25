export type ClinicalField = 'concept'|'anatomical_site'|'medication_name'|'dose_value'|'dose_unit'|'route'|'frequency'|'duration'|'allergen'|'allergy_reaction';
export type Fact = {
 fact_id:string;category:string;section:string;text:string;subject:string;assertion:string;temporality:string;
 origin:string;evidence:{segment_id:string;start_char:number;end_char:number;quote:string}|null;
 reviewed:boolean;critical_reviewed:boolean;clarification:string;excluded:boolean;
 laterality:string;clinical_source:string;extraction_version:string;
} & Record<ClinicalField,string|null>;

export const emptyFact=():Fact=>({fact_id:crypto.randomUUID(),category:'other',section:'subjective',text:'',subject:'unknown',
 assertion:'uncertain',temporality:'unknown',origin:'clinician_entered',evidence:null,reviewed:false,critical_reviewed:false,
 clarification:'',excluded:false,concept:null,anatomical_site:null,laterality:'unknown',clinical_source:'unknown',
 extraction_version:'manual_or_legacy',medication_name:null,dose_value:null,dose_unit:null,route:null,frequency:null,
 duration:null,allergen:null,allergy_reaction:null});

export function cleanFact(fact:Fact):Fact {
 const defaults=emptyFact();
 return Object.fromEntries(Object.keys(defaults).map(key=>[key,fact[key as keyof Fact]===undefined?defaults[key as keyof Fact]:fact[key as keyof Fact]])) as Fact;
}
