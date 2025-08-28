
"use strict";

let UpdateParams = require('./UpdateParams.js')
let GoTo = require('./GoTo.js')
let UploadTrajectory = require('./UploadTrajectory.js')
let Takeoff = require('./Takeoff.js')
let Land = require('./Land.js')
let NotifySetpointsStop = require('./NotifySetpointsStop.js')
let StartTrajectory = require('./StartTrajectory.js')
let Stop = require('./Stop.js')
let SetGroupMask = require('./SetGroupMask.js')

module.exports = {
  UpdateParams: UpdateParams,
  GoTo: GoTo,
  UploadTrajectory: UploadTrajectory,
  Takeoff: Takeoff,
  Land: Land,
  NotifySetpointsStop: NotifySetpointsStop,
  StartTrajectory: StartTrajectory,
  Stop: Stop,
  SetGroupMask: SetGroupMask,
};
