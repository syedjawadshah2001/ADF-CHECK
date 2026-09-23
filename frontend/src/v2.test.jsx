// @vitest-environment jsdom
import React from 'react';
import {beforeEach,afterEach,describe,it,expect,vi} from 'vitest';
import {render,screen,cleanup,fireEvent,waitFor} from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import {ReviewWorkspace,ProfileManager,DEFAULT} from './v2';

const reply=(data,status=200)=>Promise.resolve({ok:status<400,status,json:async()=>data});
const review={id:'r1',filename:'draft.docx',total:1,words:120,profile:DEFAULT,summary:{'Font Size Errors':1},sections:{'Font Size Errors':['Error: wrong size']},findings:[{id:'F1',category:'Font Size Errors',location:'P2',found:'20 pt',expected:'12 pt',explanation:'Use the profile body size.'}],readiness:{note:'Local rule-based workflow.',steps:['Profile selected','Formatting checked'],tasks:[{id:'section:Abstract',title:'Abstract section',status:'needs_review',kind:'structure',detail:'No matching heading found.'}]},acknowledged_tasks:[],assistant_history:[],approval:null,expires_at:new Date().toISOString()};
beforeEach(()=>{Element.prototype.scrollIntoView=vi.fn();});
afterEach(()=>{cleanup();vi.unstubAllGlobals();});

describe('Version 2 review workflow',()=>{
  it('requires a preview before generating an approved copy',async()=>{
    const fetch=vi.fn((url)=>url.endsWith('/preview')?reply({preview_id:'a'.repeat(64),groups:['fonts','sizes','spacing','margins','headers'],total_changes:1,counts:{sizes:1},changes:[{location:'P2',group:'sizes',field:'size',before:'20',after:'12',text:'Research'}],note:'Formatting preview.'}):reply({groups:['fonts','sizes','spacing','margins','headers'],remaining_findings:0,total_changes:1}));
    vi.stubGlobal('fetch',fetch);render(<ReviewWorkspace result={review}/>);
    await userEvent.click(screen.getByRole('tab',{name:'Download files'}));
    await userEvent.click(screen.getByRole('button',{name:'Download Corrected Word file'}));
    expect(screen.getByRole('heading',{name:'Choose what changes.'})).toBeTruthy();
    expect(fetch).not.toHaveBeenCalled();
    await userEvent.click(screen.getByRole('button',{name:'Generate preview'}));
    await screen.findByText('1 formatting-property changes');
    expect(fetch.mock.calls.some(([url])=>url.endsWith('/approve'))).toBe(false);
    await userEvent.click(screen.getByRole('button',{name:'Approve & generate copy'}));
    await screen.findByText(/Approved categories:/);
    const approval=fetch.mock.calls.find(([url])=>url.endsWith('/approve'));
    expect(JSON.parse(approval[1].body).approved).toBe(true);
  });

  it('invalidates preview when correction categories change',async()=>{
    vi.stubGlobal('fetch',vi.fn(()=>reply({preview_id:'a'.repeat(64),total_changes:0,counts:{fonts:0},changes:[],note:'Preview'})));
    render(<ReviewWorkspace result={review}/>);
    await userEvent.click(screen.getByRole('tab',{name:'Preview & approve'}));
    await userEvent.click(screen.getByRole('button',{name:'Generate preview'}));
    await screen.findByRole('button',{name:'Approve & generate copy'});
    await userEvent.click(screen.getByLabelText('Typefaces'));
    expect(screen.queryByRole('button',{name:'Approve & generate copy'})).toBeNull();
  });

  it('shows local chat evidence and opens the referenced paragraph',async()=>{
    const fetch=vi.fn(url=>url.endsWith('/config')?reply({ai_enabled:false}):url.includes('/paragraphs/')?reply({id:'P2',text:'Original paragraph evidence.',heading:'Introduction',style:'Normal',findings:[]}):reply({mode:'local',answer:'[P2] Use 12 pt body text.',citations:[{id:'P2'}],action:null}));
    vi.stubGlobal('fetch',fetch);render(<ReviewWorkspace result={review}/>);
    await userEvent.click(screen.getByRole('tab',{name:'Document assistant'}));
    await userEvent.type(screen.getByLabelText('Your question'),'Why is P2 incorrect?');
    await userEvent.click(screen.getByRole('button',{name:'Ask'}));
    await screen.findByText('[P2] Use 12 pt body text.');
    expect(screen.getByText('Local document assistant · rule-based')).toBeTruthy();
    await userEvent.click(screen.getByRole('button',{name:'P2'}));
    expect(await screen.findByText('Original paragraph evidence.')).toBeTruthy();
    await userEvent.click(screen.getByRole('button',{name:'Close paragraph'}));
    await userEvent.click(screen.getByRole('tab',{name:'Download files'}));
    await userEvent.click(screen.getByRole('tab',{name:'Document assistant'}));
    expect(screen.getByText('[P2] Use 12 pt body text.')).toBeTruthy();
    const request=fetch.mock.calls.find(([url])=>url.endsWith('/assistant'));
    expect(JSON.parse(request[1].body).use_ai).toBe(false);
  });

  it('saves custom university rules rather than a fake official profile',async()=>{
    const fetch=vi.fn((url,options)=>options.method==='POST'?reply({id:'custom',rules:DEFAULT}):reply([{id:'default',rules:DEFAULT,builtin:true}]));
    vi.stubGlobal('fetch',fetch);render(<ProfileManager/>);
    fireEvent.change(screen.getByLabelText('Profile name'),{target:{value:'Department handbook 2026'}});
    fireEvent.change(screen.getByLabelText('Body size (pt)'),{target:{value:'14'}});
    await userEvent.click(screen.getByRole('button',{name:'Save profile'}));
    await screen.findByRole('status');
    const post=fetch.mock.calls.find(([,o])=>o.method==='POST');
    expect(JSON.parse(post[1].body).body_size).toBe(14);
    expect(JSON.parse(post[1].body).name).toBe('Department handbook 2026');
  });
});
