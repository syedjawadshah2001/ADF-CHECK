// @vitest-environment jsdom
import React from 'react';
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest';
import { render, screen, fireEvent, waitFor, cleanup } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { App } from './main';

const reply = (data, status = 200) => Promise.resolve({ ok:status<400, status, json:async()=>data });
beforeEach(() => {
  window.location.hash = '#/';
  window.scrollTo = vi.fn();
  Element.prototype.scrollIntoView = vi.fn();
});
afterEach(() => { cleanup(); vi.unstubAllGlobals(); });

describe('React account and document flows', () => {
  it('shows the landing page without an account', async () => {
    vi.stubGlobal('fetch', vi.fn(() => reply({detail:'Sign in'},401)));
    render(<App/>);
    expect(await screen.findByRole('heading',{name:/Great ideas/i})).toBeTruthy();
    expect(screen.getByRole('button',{name:/Start your document review/i})).toBeTruthy();
  });

  it('submits username and password and opens the workspace', async () => {
    window.location.hash = '#/login';
    const fetch = vi.fn((url) => url.endsWith('/auth/me') ? reply({},401) : url.endsWith('/auth/login') ? reply({id:1,username:'researcher'}) : reply([]));
    vi.stubGlobal('fetch',fetch);
    render(<App/>);
    await screen.findByRole('heading',{name:'Welcome back.'});
    await userEvent.type(screen.getByLabelText('Username'),'researcher');
    await userEvent.type(screen.getByLabelText('Password'),'strong-password');
    await userEvent.click(screen.getByRole('button',{name:'Sign in'}));
    expect(await screen.findByRole('heading',{name:'Your next great submission.'})).toBeTruthy();
    const call = fetch.mock.calls.find(([url]) => url.endsWith('/auth/login'));
    expect(JSON.parse(call[1].body)).toEqual({username:'researcher',password:'strong-password'});
    expect(call[1].credentials).toBe('same-origin');
    expect(localStorage.length).toBe(0);
  });

  it('prevents mismatched signup passwords', async () => {
    window.location.hash = '#/signup';
    const fetch = vi.fn(() => reply({},401));
    vi.stubGlobal('fetch',fetch);
    render(<App/>);
    await screen.findByRole('heading',{name:'Create your account.'});
    await userEvent.type(screen.getByLabelText('Username'),'researcher');
    await userEvent.type(screen.getByLabelText('Password'),'strong-password');
    await userEvent.type(screen.getByLabelText('Confirm password'),'different-password');
    await userEvent.click(screen.getByRole('button',{name:'Create account'}));
    expect(await screen.findByRole('alert')).toHaveProperty('textContent','Your passwords do not match.');
    expect(fetch.mock.calls.some(([url]) => url.endsWith('/auth/signup'))).toBe(false);
  });

  it('uploads a Word document and exposes all three downloads', async () => {
    const review = {id:'review1',filename:'research.docx',total:1,words:100,summary:{'Margin Errors':1},sections:{'Margin Errors':['Error: Margin not set to 1 inch.']},expires_at:new Date().toISOString(),created_at:new Date().toISOString()};
    vi.stubGlobal('fetch',vi.fn((url, options) => url.endsWith('/auth/me') ? reply({id:1,username:'researcher'}) : options.method==='POST' ? reply(review,201) : reply([])));
    render(<App/>);
    const input = await screen.findByLabelText('Choose Word document');
    await userEvent.upload(input,new File(['test-content'],'research.docx',{type:'application/vnd.openxmlformats-officedocument.wordprocessingml.document'}));
    await userEvent.click(screen.getByRole('button',{name:'Analyze document'}));
    expect(await screen.findByRole('heading',{name:'Clarity, down to the details.'})).toBeTruthy();
    await userEvent.click(screen.getByRole('tab',{name:'Download files'}));
    expect(screen.getAllByRole('button',{name:/Download .*file|Download PDF/})).toHaveLength(3);
  });

  it('shows invalid file feedback without submitting a request', async () => {
    const fetch = vi.fn((url) => url.endsWith('/auth/me') ? reply({id:1,username:'researcher'}) : reply([]));
    vi.stubGlobal('fetch',fetch);
    render(<App/>);
    const input = await screen.findByLabelText('Choose Word document');
    fireEvent.change(input,{target:{files:[new File(['text'],'bad.txt')]}});
    expect(screen.getByRole('alert').textContent).toContain('Word .docx');
    expect(screen.getByRole('button',{name:'Analyze document'}).disabled).toBe(true);
  });
});
