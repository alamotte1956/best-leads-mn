"""Lead-alert choices do not change matching, account approval or SMS consent."""
from datetime import datetime, timezone
from flask import Blueprint, abort, flash, redirect, render_template, request, session, url_for
from sqlalchemy import update
from sqlalchemy.exc import IntegrityError
from operations import contractor_required
from national import administrator
from contractor_onboarding import require_csrf
from consumer_requests import PRIVATE_HEADERS

notification_preferences = Blueprint('notification_preferences',__name__)


class PreferenceConflict(RuntimeError):
    pass


def define_notification_preferences(db):
    class NotificationPreference(db.Model):
        __tablename__ = 'contractor_notification_preferences'
        contractor_id = db.Column(db.Integer,db.ForeignKey('contractors.id'),primary_key=True)
        lead_email = db.Column(db.Boolean,nullable=False)
        lead_sms = db.Column(db.Boolean,nullable=False)
        version = db.Column(db.Integer,nullable=False)
        updated_at = db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
        __table_args__ = (db.CheckConstraint('version > 0',name='notification_preference_version'),)
    class NotificationPreferenceEvent(db.Model):
        __tablename__ = 'contractor_notification_events'
        id = db.Column(db.Integer,primary_key=True)
        contractor_id = db.Column(db.Integer,db.ForeignKey('contractors.id'),nullable=False,index=True)
        previous_email = db.Column(db.Boolean,nullable=False)
        previous_sms = db.Column(db.Boolean,nullable=False)
        lead_email = db.Column(db.Boolean,nullable=False)
        lead_sms = db.Column(db.Boolean,nullable=False)
        created_at = db.Column(db.DateTime(timezone=True),nullable=False,default=db.func.now())
    return NotificationPreference,NotificationPreferenceEvent


def current_choices(contractor_id):
    from app import NotificationPreference
    row=NotificationPreference.query.filter_by(contractor_id=contractor_id).populate_existing().first()
    return {'lead_email':row.lead_email,'lead_sms':row.lead_sms,'version':row.version} if row else {
        'lead_email':True,'lead_sms':True,'version':0}


def lead_alert_enabled(contractor_id,channel):
    if channel not in ('email','sms'):return False
    return current_choices(contractor_id)['lead_'+channel] is True


@notification_preferences.after_request
def private_response(response):
    response.headers.update(PRIVATE_HEADERS)
    return response


def preference_context(contractor):
    from app import contractor_sms_eligible, NotificationPreferenceEvent
    from email_delivery import email_suppressed
    return dict(contractor=contractor,choices=current_choices(contractor.id),
        sms_permitted=contractor_sms_eligible(contractor,include_preferences=False),email_blocked=email_suppressed(contractor.email),
        history=NotificationPreferenceEvent.query.filter_by(contractor_id=contractor.id).order_by(
            NotificationPreferenceEvent.id.desc()).limit(10).all())


@notification_preferences.route('/contractor/notifications',methods=['GET','POST'])
@contractor_required
def settings(contractor):
    from app import db, Contractor, Delivery, NotificationPreference, NotificationPreferenceEvent
    from contractor_session_security import contractor_session_valid
    error=None;code=200
    if request.method=='POST':
        require_csrf()
        revision=request.form.get('version','')
        if not revision.isascii() or not revision.isdigit() or len(revision)>9:abort(400)
        for key in ('lead_email','lead_sms'):
            if request.form.getlist(key) not in ([],['yes']):abort(400)
        desired={'lead_email':request.form.get('lead_email')=='yes','lead_sms':request.form.get('lead_sms')=='yes'}
        try:
            contractor=Contractor.query.filter_by(id=contractor.id).populate_existing().with_for_update().one()
            if not contractor_session_valid(dict(session),contractor):abort(403)
            previous=current_choices(contractor.id)
            if int(revision)!=previous['version'] and any(desired[key]!=previous[key] for key in desired):
                error='Your choices changed in another session. The current choices are shown below; review them before saving again.';code=409
                db.session.rollback()
            elif any(desired[key]!=previous[key] for key in desired):
                if previous['version']==0:
                    db.session.add(NotificationPreference(contractor_id=contractor.id,version=1,**desired))
                    db.session.flush()
                else:
                    changed=db.session.execute(update(NotificationPreference).where(
                        NotificationPreference.contractor_id==contractor.id,
                        NotificationPreference.version==previous['version']).values(
                        **desired,version=previous['version']+1,updated_at=datetime.now(timezone.utc))).rowcount
                    if changed!=1:raise PreferenceConflict()
                db.session.add(NotificationPreferenceEvent(contractor_id=contractor.id,
                    previous_email=previous['lead_email'],previous_sms=previous['lead_sms'],**desired))
                disabled=[channel for channel in ('email','sms') if not desired['lead_'+channel]]
                if disabled:
                    db.session.execute(update(Delivery).where(Delivery.contractor_id==contractor.id,
                        Delivery.offer_id.is_not(None),Delivery.channel.in_(disabled),Delivery.status=='pending'
                    ).values(status='suppressed'))
                db.session.commit()
                flash('Lead-alert choices saved. Existing offers remain in your dashboard.','success')
                return redirect(url_for('notification_preferences.settings'),code=303)
            else:
                db.session.rollback()
                flash('Your lead-alert choices are already up to date.','success')
                return redirect(url_for('notification_preferences.settings'),code=303)
        except (IntegrityError,PreferenceConflict):
            db.session.rollback();error='Your choices changed in another session. Review the current choices and save again.';code=409
        except Exception:
            db.session.rollback();raise
    return render_template('notification_preferences.html',error=error,readonly=False,**preference_context(contractor)),code


@notification_preferences.get('/admin/contractors/<int:contractor_id>/notifications')
@administrator
def inspect(contractor_id):
    from app import db,Contractor
    contractor=db.session.get(Contractor,contractor_id)
    if not contractor:abort(404)
    return render_template('notification_preferences.html',error=None,readonly=True,**preference_context(contractor))
